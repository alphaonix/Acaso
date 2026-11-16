"""DETECTOR DE ANOMALIA com DIAGNOSTICO DE ORIGEM.

Problema: a taxa de retorno de um pais estava em 25% e, depois de uma carga, foi para 97%. Pode ser (a) o dado que chegou mudou (problema do
sistema de origem), (b) uma transformacao nossa (silver ou gold) errou, ou (c) o comportamento real mudou. Quanto mais cedo se sabe qual,
mais rapido se resolve. Este modulo faz as duas coisas:
  1. DETECTA: compara a taxa de retorno em 7 dias de cada pais com a da carga anterior (teste de duas proporcoes). So aponta quando a
     mudanca e grande (>= 5 pontos percentuais) E improvavel de ser acaso (z >= 4), e so em paises com 30 ou mais elegiveis.
  2. DIAGNOSTICA: percorre o funil camada por camada (bronze -> silver -> gold) comparando as medidas da carga atual com as da anterior e
     diz ONDE a mudanca comecou:
        GOLD            a gold nao bate com a silver (erro de agregacao)
        TRANSFORMACAO   os arquivos de entrada sao identicos e o resultado mudou (regra, parametro ou codigo mudou)
        BRONZE          o dado de entrada mudou de padrao (linhas, enderecos distintos, vazios): problema da fonte, nao do ETL
        SILVER          a entrada esta normal, mas a limpeza/pessoa/elegibilidade se comportou diferente
        SEM CAUSA       tudo estavel e a taxa mudou mesmo assim: pode ser mudanca real de comportamento
Tudo e calculado a partir de auditoria.metrica (historico de todas as cargas): nao le o dado de novo.
"""
import json
import math
from dataclasses import dataclass, field

from . import deriva
from .qualidade import Resultado

PP_MINIMO = 5.0          # mudanca minima da taxa, em pontos percentuais
Z_MINIMO = 4.0           # e o quanto ela tem de ser improvavel de ser acaso
AMOSTRA_MINIMA = 30      # menos elegiveis que isso: nao se avalia (mesma regra do painel)
# sinais do funil: a partir de quanto uma etapa e considerada "mudou de padrao"
LIM_LINHAS_PCT, LIM_IPS_PCT, LIM_NULOS_PP, LIM_EXCLUSAO_PP, LIM_PESSOAS_CONV_PCT, LIM_ELEGIVEIS_PP = 30.0, 20.0, 5.0, 5.0, 20.0, 10.0
LIM_PESSOAS_ENDERECO_PCT = 10.0     # pessoas por endereco: no incidente do PDF, 2.385 enderecos viraram 2.895 pessoas (+21%) por causa do navegador


@dataclass
class Sinal:
    camada: str
    etapa: str
    antes: float | None
    agora: float | None
    unidade: str            # "n" contagem, "%" percentual (0 a 1), "x" razao
    suspeito: bool

    def formatar(self, v) -> str:
        if v is None:
            return "-"
        return f"{v * 100:.1f}%" if self.unidade == "%" else (f"{v:.3f}" if self.unidade == "x" else f"{v:,.0f}".replace(",", "."))

    def texto(self) -> str:
        return f"{self.etapa}: {self.formatar(self.antes)} -> {self.formatar(self.agora)}"


@dataclass
class Anomalia:
    pais: str
    taxa_ref: float
    taxa_atual: float
    n_ref: int
    n_atual: int
    z: float
    origem: str             # GOLD | TRANSFORMACAO | BRONZE | SILVER | SEM_CAUSA
    resumo: str
    sinais: list[Sinal] = field(default_factory=list)
    tipo: str = "TAXA"      # TAXA: a taxa saltou | ENTRADA / LIMPEZA / AGREGACAO: a taxa nao se mexeu, mas a bronze / a silver mudou de padrao ou a gold nao bate com a silver


# ------------------------------------------------------------------ leitura das medidas
def carregar(ops, carga: int) -> dict:
    linhas = ops.execute("SELECT camada, metrica, escopo, valor FROM auditoria.metrica WHERE execucao_id = %s AND valor IS NOT NULL", (carga,)).fetchall()
    return {(c, m, e): float(v) for c, m, e, v in linhas}


def _div(a, b):
    return None if a is None or not b else a / b


def perfil(m: dict, pais: str) -> dict:
    """As medidas de um pais, camada por camada, a partir do historico."""
    b = "(vazio)" if pais == "Desconhecido" else pais              # a bronze chama de "(vazio)" o que a silver chama de "Desconhecido"
    g = lambda camada, nome, escopo: m.get((camada, nome, escopo))
    linhas = g("bronze", "linhas_por_pais", b)
    p = {"linhas": linhas, "ips": g("bronze", "ips_distintos_por_pais", b),
         "conversas": g("silver", "conversas", pais), "pessoas": g("silver", "pessoas", pais),
         "elegiveis": g("silver", "pessoas_elegiveis", pais), "voltaram": g("silver", "voltaram_7d", pais),
         "gold_elegiveis": g("gold", "pais_elegiveis", pais), "gold_voltaram": g("gold", "pais_voltaram", pais)}
    for col in ("hashed_ip", "inicio", "user_agent"):
        p["nulos_" + col] = _div(g("bronze", "nulos_por_pais", f"{b}|{col}"), linhas)
    p["ips_por_linha"] = _div(p["ips"], linhas)
    p["exclusao"] = None if p["conversas"] is None or not linhas else 1 - p["conversas"] / linhas
    p["pessoas_por_conversa"] = _div(p["pessoas"], p["conversas"])
    p["share_elegiveis"] = _div(p["elegiveis"], p["pessoas"])
    p["pessoas_por_endereco"] = _div(p["pessoas"], p["ips"])           # perto de 1; sobe quando o mesmo endereco vira varias pessoas (incidente do navegador atualizado)
    p["taxa"] = _div(p["voltaram"], p["elegiveis"])
    p["share24"] = _div(g("silver", "voltaram_24h", pais), p["voltaram"])          # dos que voltaram em 7 dias, quantos ja tinham voltado em 24 h
    return p


def _z(k1, n1, k0, n0) -> float:
    """Teste de duas proporcoes (atual contra referencia)."""
    p1, p0, pool = k1 / n1, k0 / n0, (k1 + k0) / (n1 + n0)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n0))
    return (p1 - p0) / se if se > 0 else (math.inf if p1 != p0 else 0.0)


# ------------------------------------------------------------------ diagnostico do funil
def _sinais(a: dict, r: dict) -> list[Sinal]:
    def rel(x, y):       # variacao relativa em %, nula se nao der para calcular
        return None if x is None or y is None or y == 0 else abs(x - y) / abs(y) * 100

    def pp(x, y):
        return None if x is None or y is None else abs(x - y) * 100

    def sus(v, lim):
        return v is not None and v >= lim

    s = [Sinal("bronze", "linhas do pais", r["linhas"], a["linhas"], "n", sus(rel(a["linhas"], r["linhas"]), LIM_LINHAS_PCT)),
         Sinal("bronze", "enderecos distintos por linha", r["ips_por_linha"], a["ips_por_linha"], "x", sus(rel(a["ips_por_linha"], r["ips_por_linha"]), LIM_IPS_PCT))]
    for col, nome in (("hashed_ip", "sem endereco"), ("inicio", "sem horario de inicio"), ("user_agent", "sem navegador")):
        s.append(Sinal("bronze", f"linhas {nome}", r["nulos_" + col], a["nulos_" + col], "%", sus(pp(a["nulos_" + col], r["nulos_" + col]), LIM_NULOS_PP)))
    s += [Sinal("silver", "conversas descartadas na limpeza", r["exclusao"], a["exclusao"], "%", sus(pp(a["exclusao"], r["exclusao"]), LIM_EXCLUSAO_PP)),
          Sinal("silver", "pessoas por conversa", r["pessoas_por_conversa"], a["pessoas_por_conversa"], "x",
                sus(rel(a["pessoas_por_conversa"], r["pessoas_por_conversa"]), LIM_PESSOAS_CONV_PCT)),
          Sinal("silver", "pessoas por endereco (sobe se a mesma pessoa for contada varias vezes)", r["pessoas_por_endereco"], a["pessoas_por_endereco"], "x",
                sus(rel(a["pessoas_por_endereco"], r["pessoas_por_endereco"]), LIM_PESSOAS_ENDERECO_PCT)),
          Sinal("silver", "elegiveis entre as pessoas", r["share_elegiveis"], a["share_elegiveis"], "%", sus(pp(a["share_elegiveis"], r["share_elegiveis"]), LIM_ELEGIVEIS_PP)),
          Sinal("silver", "voltaram em 24 h entre os que voltaram em 7 dias", r["share24"], a["share24"], "%", sus(pp(a["share24"], r["share24"]), LIM_ELEGIVEIS_PP)),
          Sinal("silver", "pessoas elegiveis (denominador)", r["elegiveis"], a["elegiveis"], "n", False),
          Sinal("silver", "voltaram em 7 dias (numerador)", r["voltaram"], a["voltaram"], "n", False)]
    for nome, silver_, gold_ in (("elegiveis", a["elegiveis"], a["gold_elegiveis"]), ("voltaram", a["voltaram"], a["gold_voltaram"])):
        s.append(Sinal("gold", f"{nome}: silver -> gold (devem ser iguais)", silver_, gold_, "n", gold_ is not None and gold_ != silver_))
    return s


def _origem(sinais: list[Sinal], mesma_semente: bool) -> tuple[str, str]:
    lista = lambda c: "; ".join(x.texto() for x in sinais if x.camada == c and x.suspeito)
    if any(x.camada == "gold" and x.suspeito for x in sinais):
        return "GOLD", "a gold nao bate com a silver para este pais: erro de agregacao em etl/camadas/gold/sql.py"
    if mesma_semente:
        return "TRANSFORMACAO", ("os arquivos de entrada sao identicos aos da carga anterior e o resultado mudou: uma regra, parametro ou o codigo do ETL mudou "
                                 "(veja auditoria.mudancas_entre_cargas e o ultimo commit)")
    if lista("bronze"):
        return "BRONZE", f"o dado que chegou mudou de padrao ({lista('bronze')}): provavel problema na fonte, nao no ETL. Confira os arquivos de origem antes de mexer no codigo"
    if lista("silver"):
        return "SILVER", (f"a entrada parece normal, mas a limpeza ou as regras de pessoa/visita/elegibilidade se comportaram diferente ({lista('silver')}): "
                          "investigue etl/camadas/silver/sql.py com auditoria.registro_excluido")
    return "SEM_CAUSA", ("entrada, limpeza e agregacao estao estaveis e a taxa mudou mesmo assim: pode ser mudanca real de comportamento. "
                         "Confirme com a fonte antes de publicar")


def detectar(atual: dict, ref: dict, mesma_semente: bool) -> list[Anomalia]:
    """Paises cuja taxa de retorno em 7 dias saltou ou caiu muito em relacao a carga de referencia, cada um com o diagnostico de origem."""
    saida = []
    paises = sorted({e for (c, mt, e) in atual if c == "silver" and mt == "pessoas_elegiveis"})
    for pais in paises:
        a, r = perfil(atual, pais), perfil(ref, pais)
        if None in (a["taxa"], r["taxa"]) or a["elegiveis"] < AMOSTRA_MINIMA or r["elegiveis"] < AMOSTRA_MINIMA:
            continue
        # a taxa e olhada na silver E na gold: o painel mostra a da gold, e um erro so da gold nao aparece na silver
        candidatos = []
        for k_a, n_a, k_r, n_r in ((a["voltaram"], a["elegiveis"], r["voltaram"], r["elegiveis"]),
                                   (a["gold_voltaram"], a["gold_elegiveis"], r["gold_voltaram"], r["gold_elegiveis"])):
            if None in (k_a, n_a, k_r, n_r) or n_a < AMOSTRA_MINIMA or n_r < AMOSTRA_MINIMA:
                continue
            z = _z(k_a, n_a, k_r, n_r)
            if abs(k_a / n_a - k_r / n_r) * 100 >= PP_MINIMO and abs(z) >= Z_MINIMO:
                candidatos.append((abs(z), z, k_a / n_a, k_r / n_r, n_a, n_r))
        sinais = _sinais(a, r)
        if candidatos:
            _, z, taxa_a, taxa_r, n_a, n_r = max(candidatos)
            origem, resumo = _origem(sinais, mesma_semente)
            saida.append(Anomalia(pais, taxa_r, taxa_a, int(n_r), int(n_a), z, origem, resumo, sinais))
        elif any(s.camada == "gold" and s.suspeito for s in sinais):
            # a taxa NAO se mexeu, mas a gold (o que a tela mostra) nao bate com a silver: erro de agregacao que a taxa sozinha esconde
            # (achado da simulacao: um pais que herda os numeros de outro com taxa parecida)
            saida.append(Anomalia(pais, r["taxa"], a["taxa"], int(r["elegiveis"]), int(a["elegiveis"]), 0.0, "GOLD",
                                  "a taxa quase nao mudou, mas a gold nao bate com a silver ("
                                  + "; ".join(s.texto() for s in sinais if s.camada == "gold" and s.suspeito)
                                  + "): erro de agregacao em etl/camadas/gold/sql.py", sinais, "AGREGACAO"))
        elif any(s.camada == "bronze" and s.suspeito for s in sinais):
            # a taxa NAO se mexeu, mas o dado de entrada mudou de padrao (ex.: 60% das linhas sem endereco encolhem o pais todo sem mudar a taxa).
            # E o caso em que olhar so a taxa deixaria passar um defeito da fonte; aponta antes que ele se agrave.
            saida.append(Anomalia(pais, r["taxa"], a["taxa"], int(r["elegiveis"]), int(a["elegiveis"]), 0.0, "BRONZE",
                                  "a taxa quase nao mudou, mas o dado de entrada mudou de padrao ("
                                  + "; ".join(s.texto() for s in sinais if s.camada == "bronze" and s.suspeito)
                                  + "): provavel problema na fonte. Confira os arquivos de origem", sinais, "ENTRADA"))
        elif any(s.camada == "silver" and s.suspeito for s in sinais):
            # a taxa NAO se mexeu, a entrada esta normal, mas a limpeza/as regras da silver mudaram de comportamento (ex.: um filtro novo descarta metade das conversas)
            saida.append(Anomalia(pais, r["taxa"], a["taxa"], int(r["elegiveis"]), int(a["elegiveis"]), 0.0, "SILVER",
                                  "a taxa quase nao mudou e a entrada esta normal, mas a silver mudou de comportamento ("
                                  + "; ".join(s.texto() for s in sinais if s.camada == "silver" and s.suspeito)
                                  + "): investigue etl/camadas/silver/sql.py e auditoria.registro_excluido", sinais, "LIMPEZA"))
    return saida


def relatorio(an: Anomalia) -> list[str]:
    """O 'print' do funil: etapa por etapa, antes e agora, com a marca de onde a mudanca comecou."""
    nomes = {"GOLD": "GOLD (agregacao)", "TRANSFORMACAO": "TRANSFORMACAO (regra/codigo)", "BRONZE": "BRONZE (dado de entrada)",
             "SILVER": "SILVER (limpeza e regras)", "SEM_CAUSA": "SEM CAUSA TECNICA APARENTE"}
    z = "muito alto" if math.isinf(an.z) else f"{an.z:.1f}"
    cab = (f"retorno em 7 dias {an.taxa_ref * 100:.1f}% -> {an.taxa_atual * 100:.1f}% (elegiveis {an.n_ref} -> {an.n_atual}; z = {z})" if an.tipo == "TAXA"
           else f"{ {'ENTRADA': 'DADO DE ENTRADA MUDOU DE PADRAO', 'LIMPEZA': 'LIMPEZA DA SILVER MUDOU DE PADRAO', 'AGREGACAO': 'GOLD NAO BATE COM A SILVER'}[an.tipo] } "
                f"(retorno em 7 dias {an.taxa_ref * 100:.1f}% -> {an.taxa_atual * 100:.1f}%, elegiveis {an.n_ref} -> {an.n_atual})")
    linhas = [f"[anomalia] {an.pais}: {cab}",
              f"[anomalia]   ORIGEM PROVAVEL: {nomes[an.origem]}: {an.resumo}"]
    camada_atual = ""
    for s in an.sinais:
        if s.camada != camada_atual:
            camada_atual = s.camada
            linhas.append(f"[anomalia]   --- {camada_atual.upper()} ---")
        linhas.append(f"[anomalia]   {'!! ' if s.suspeito else '   '}{s.texto()}")
    return linhas


# ------------------------------------------------------------------ simulacao (so na memoria: nao grava nada no banco)
CAMADAS_SIMULAVEIS = ("bronze", "silver", "gold", "transformacao")


def simular(m: dict, pais: str, camada: str) -> tuple[dict, bool]:
    """Copia das medidas da ultima carga com um defeito plantado so para este pais, na camada escolhida. Devolve (medidas, mesma_semente)."""
    n = dict(m)
    b = "(vazio)" if pais == "Desconhecido" else pais

    def vezes(c, nome, escopo, f):
        n[(c, nome, escopo)] = round(n[(c, nome, escopo)] * f)

    if camada == "gold":                                         # a agregacao da gold erra e a silver continua certa
        vezes("gold", "pais_voltaram", pais, 3)
        return n, False
    if camada == "bronze":                                       # a fonte passa a mandar 60% das linhas sem endereco
        n[("bronze", "nulos_por_pais", f"{b}|hashed_ip")] = round(0.6 * n[("bronze", "linhas_por_pais", b)])
    for c, nome in (("silver", "pessoas_elegiveis"), ("gold", "pais_elegiveis")):   # silver/transformacao: os elegiveis encolhem (a regra errou)
        vezes(c, nome, pais, 0.3)
    if camada == "bronze":
        for nome in ("conversas", "pessoas"):
            vezes("silver", nome, pais, 0.4)
    return n, camada == "transformacao"


def main(argv: list[str]) -> int:
    """Sem argumentos: reanalisa a ultima carga contra a anterior. `--simular PAIS CAMADA`: planta um defeito na memoria e mostra o diagnostico."""
    from . import banco
    ops = banco.conectar(autocommit=True)
    ultima = deriva.carga_anterior(ops, 2 ** 62)
    anterior = deriva.carga_anterior(ops, ultima) if ultima else None
    if ultima is None or anterior is None:
        print("E preciso ter ao menos duas cargas bem-sucedidas para comparar.")
        return 0
    atual, ref = carregar(ops, ultima), carregar(ops, anterior)
    mesma = deriva.semente_id(ops, ultima) == deriva.semente_id(ops, anterior)
    if "--simular" in argv:
        i = argv.index("--simular")
        pais, camada = argv[i + 1], argv[i + 2]
        if camada not in CAMADAS_SIMULAVEIS:
            print(f"Camada deve ser uma de: {', '.join(CAMADAS_SIMULAVEIS)}")
            return 2
        print(f"SIMULACAO (so na memoria, nada e gravado): defeito plantado em '{camada}' para {pais}, comparado com a carga {ultima}.\n")
        ref = carregar(ops, ultima)                    # a carga mais recente e a referencia; o defeito e plantado numa copia dela
        atual, mesma = simular(ref, pais, camada)
    achadas = detectar(atual, ref, mesma)
    print(f"Carga {ultima} contra a carga {anterior}: {len(achadas)} anomalia(s).")
    for a in achadas:
        print("\n".join(l.replace("[anomalia] ", "") for l in relatorio(a)))
    return 1 if achadas and "--simular" not in argv else 0


# ------------------------------------------------------------------ dentro da carga
def verificar(ops, exec_id: int) -> list[Resultado]:
    """Chamado ao fim da gold: compara esta carga com a anterior, imprime o diagnostico e grava em auditoria.anomalia. Anomalia RETEM a carga (main.py) ate alguem aprovar com --aprovar-anomalias."""
    nome = (f"Anomalia: nenhum pais com 30 ou mais elegiveis teve a taxa de retorno em 7 dias mudada em {PP_MINIMO:.0f} pontos percentuais ou mais "
            f"(z >= {Z_MINIMO:.0f}) em relacao a carga anterior")
    ref = deriva.carga_anterior(ops, exec_id)
    if ref is None:
        return [Resultado("anomalia", nome, "sem carga anterior", "sem carga anterior", True)]
    achadas = detectar(carregar(ops, exec_id), carregar(ops, ref), deriva.semente_id(ops, exec_id) == deriva.semente_id(ops, ref))
    ops.execute("DELETE FROM auditoria.anomalia WHERE execucao_id = %s", (exec_id,))
    for a in achadas:
        for linha in relatorio(a):
            print(linha, flush=True)
        ops.execute("""INSERT INTO auditoria.anomalia (execucao_id, execucao_referencia, pais, taxa_referencia, taxa_atual, elegiveis_referencia, elegiveis_atual, z, origem, resumo, tipo, sinais)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (exec_id, ref, a.pais, a.taxa_ref, a.taxa_atual, a.n_ref, a.n_atual, None if math.isinf(a.z) else a.z, a.origem, a.resumo, a.tipo,
                     json.dumps([{"camada": s.camada, "etapa": s.etapa, "antes": s.antes, "agora": s.agora, "unidade": s.unidade, "suspeito": s.suspeito} for s in a.sinais])))
    return [Resultado("anomalia", f"{nome} (carga anterior: {ref})", "0", str(len(achadas)), not achadas)]


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
