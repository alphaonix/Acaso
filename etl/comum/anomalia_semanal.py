"""ALERTA SEMANAL: pega picos de UMA semana, como o incidente do PDF (4.2).

O detector por carga (anomalia.py) compara a taxa do pais INTEIRO com a da carga anterior. Um pico de uma semana some nessa media: no incidente,
os "novos" de uma semana quase dobraram (1.210 -> 2.034), os que voltaram ficaram iguais (375 -> 366) e a taxa da semana caiu de 31% para 18%.
Aqui cada semana e comparada com as SEIS semanas anteriores da propria carga (nao precisa de carga anterior), por tres sinais:
  1. novos      subiu 50% ou mais (ou caiu 70% ou mais) E o desvio e grande para a variacao NORMAL do pais (desvio robusto >= 5)
  2. taxa       mudou 5 pontos percentuais ou mais E z >= 4, em semanas com 30 ou mais elegiveis
  3. endereco   a proporcao de "novos" cujo endereco JA TINHA APARECIDO com outra pessoa subiu 15 pontos percentuais ou mais (z >= 4).
                Este e o sinal mais direto de PESSOA DIVIDIDA: quem ja usava o produto foi contado como gente nova
                (no incidente, o navegador atualizou e a mesma pessoa virou duas). Nao depende de o pico de novos ser enorme.
Para cada semana apontada, diz o que parece ter acontecido e em que camada procurar:
  PESSOA_DIVIDIDA     muitos "novos" tem endereco ja conhecido                                    -> SILVER (regra de pessoa)
  DENOMINADOR_INFLADO novos subiram e quem voltou nao, sem a pista do endereco                  -> SILVER ou BRONZE (duplicatas, regra de pessoa)
  PICO_DE_USO         novos e quem voltou subiram juntos: parece uso real (campanha, lancamento) -> sem causa tecnica (alarme falso provavel)
  QUEDA_DE_NOVOS      poucos novos: perda de dados na entrada?                                   -> BRONZE
  TAXA_SEMANAL        a taxa da semana mudou sem os novos mudarem                                -> SILVER (regra de retorno/elegibilidade) ou mudanca real
So gera ALERTA para o que e NOVO desde a carga anterior (o que ja existia nos dados e conhecido, e fica registrado em auditoria.anomalia_semanal).
Os limites foram calibrados nos dados reais: com 30% e z=4 para os novos, 202 paises geravam 406 alertas (ruido); com os de agora, dezenas.
"""
import math
import statistics
from dataclasses import dataclass

from .anomalia import _z
from .qualidade import Resultado

JANELA = 6                 # semanas anteriores usadas como referencia
MIN_ANTERIORES = 4         # minimo de semanas anteriores para avaliar
MIN_NOVOS_BASE = 25        # mediana de novos abaixo disso: pais pequeno demais para avaliar
PCT_ALTA, PCT_QUEDA, Z_NOVOS = 50.0, 70.0, 5.0
PP_TAXA, Z_TAXA, MIN_ELEGIVEIS = 5.0, 4.0, 30
PP_ENDERECO, Z_ENDERECO, MIN_NOVOS_ENDERECO = 15.0, 4.0, 20
CAMADA = {"PESSOA_DIVIDIDA": "SILVER", "DENOMINADOR_INFLADO": "SILVER_OU_BRONZE", "PICO_DE_USO": "SEM_CAUSA", "QUEDA_DE_NOVOS": "BRONZE", "TAXA_SEMANAL": "SILVER"}


@dataclass
class Semana:
    semana: str
    novos: int
    elegiveis: int
    voltaram: int


@dataclass
class AlertaSemanal:
    pais: str
    semana: str
    diagnostico: str
    novos: int
    novos_base: float
    voltaram: int
    voltaram_base: float
    taxa: float | None
    taxa_base: float | None
    pct_endereco: float | None = None
    pct_endereco_base: float | None = None
    resumo: str = ""

    @property
    def camada(self) -> str:
        return CAMADA[self.diagnostico]

    @property
    def chave(self) -> tuple:
        return (self.pais, self.semana, self.diagnostico)


def _taxa(v, e):
    return None if not e else v / e


def _pico(w: Semana, ant: list[Semana]) -> int:
    """+1 se os novos da semana subiram demais, -1 se cairam demais, 0 se estao dentro do normal. Escala robusta: a mediana dos desvios das semanas anteriores."""
    xs = [p.novos for p in ant]
    base = statistics.median(xs)
    escala = max(statistics.median(abs(x - base) for x in xs) * 1.4826, math.sqrt(base))
    desv = w.novos - base
    if desv > 0 and desv / base * 100 >= PCT_ALTA and desv / escala >= Z_NOVOS:
        return 1
    if desv < 0 and -desv / base * 100 >= PCT_QUEDA and -desv / escala >= Z_NOVOS:
        return -1
    return 0


def _endereco(w: Semana, ant: list[Semana], end: dict | None) -> tuple[float | None, float | None, bool]:
    """(% dos novos da semana com endereco ja conhecido, o normal das semanas anteriores, se o salto e alerta)."""
    if not end or w.semana not in end:
        return None, None, False
    n, jv = end[w.semana]
    antes = [end[p.semana] for p in ant if p.semana in end]
    n0, k0 = sum(x[0] for x in antes), sum(x[1] for x in antes)
    if n < MIN_NOVOS_ENDERECO or n0 < MIN_NOVOS_ENDERECO:
        return None, None, False
    pct, base = jv / n * 100, k0 / n0 * 100
    return pct, base, pct - base >= PP_ENDERECO and _z(jv, n, k0, n0) >= Z_ENDERECO


def sinalizadas(series: dict[str, list[Semana]], enderecos: dict[str, dict] | None = None) -> list[tuple[str, Semana, list[Semana]]]:
    """Semanas que passam em um dos tres testes. Devolve (pais, semana, anteriores)."""
    saida = []
    for pais, sem in series.items():
        for i in range(MIN_ANTERIORES, len(sem)):
            ant, w = sem[max(0, i - JANELA):i], sem[i]
            base = statistics.median(p.novos for p in ant)
            if base < MIN_NOVOS_BASE:
                continue
            ultima = i == len(sem) - 1                                # a ultima semana pode estar incompleta: so conta se os novos forem ALTOS
            p = _pico(w, ant)
            f_novos = p == 1 or (p == -1 and not ultima)
            ke, kv = sum(a.elegiveis for a in ant), sum(a.voltaram for a in ant)
            f_taxa = False
            if w.elegiveis >= MIN_ELEGIVEIS and ke >= MIN_ELEGIVEIS:
                f_taxa = abs(_taxa(w.voltaram, w.elegiveis) - kv / ke) * 100 >= PP_TAXA and abs(_z(w.voltaram, w.elegiveis, kv, ke)) >= Z_TAXA
            f_end = _endereco(w, ant, (enderecos or {}).get(pais))[2]
            if f_novos or f_taxa or f_end:
                saida.append((pais, w, ant))
    return saida


def diagnosticar(pais: str, w: Semana, ant: list[Semana], end: dict | None = None) -> AlertaSemanal:
    """Decide o que parece ter acontecido naquela semana. `end`: {semana: (novos, com endereco ja visto)} do pais, ou None."""
    base_n = statistics.median(p.novos for p in ant)
    base_v = statistics.median(p.voltaram for p in ant)
    ke, kv = sum(p.elegiveis for p in ant), sum(p.voltaram for p in ant)
    taxa, taxa_base = _taxa(w.voltaram, w.elegiveis), _taxa(kv, ke)
    rel_n = (w.novos - base_n) / base_n * 100
    rel_v = (w.voltaram - base_v) / max(base_v, 5) * 100          # com poucos retornos na base, compara com 5 (evita dividir por zero)
    pct, base_pct, f_end = _endereco(w, ant, end)
    a = AlertaSemanal(pais, w.semana, "TAXA_SEMANAL", w.novos, base_n, w.voltaram, base_v, taxa, taxa_base, pct, base_pct)
    pico = _pico(w, ant)
    if f_end:
        a.diagnostico = "PESSOA_DIVIDIDA"
        a.resumo = (f"{pct:.0f}% dos 'novos' da semana ({w.novos} contra {base_n:.0f} nas anteriores) usam um endereco que ja tinha aparecido com outra pessoa "
                    f"(normal: {base_pct:.0f}%), e quem voltou ficou em {w.voltaram} (normal {base_v:.0f}). Gente que ja usava o produto esta sendo contada como nova, como no incidente "
                    "do navegador atualizado: veja a regra de pessoa (UA_NORM_SQL) em etl/comum/definicoes.py e o recalculo independente")
    elif pico == 0:
        a.resumo = (f"a taxa da semana foi {taxa * 100:.1f}% contra {taxa_base * 100:.1f}% nas semanas anteriores, com os novos normais ({w.novos} contra {base_n:.0f}): "
                    "confira a regra de retorno e de elegibilidade da silver; pode ser mudanca real")
    elif pico == -1:
        a.diagnostico = "QUEDA_DE_NOVOS"
        a.resumo = f"so {w.novos} novos contra {base_n:.0f} nas semanas anteriores ({rel_n:+.0f}%): perda de dados na entrada? compare as linhas por semana na bronze"
    elif rel_v < rel_n / 2:
        a.diagnostico = "DENOMINADOR_INFLADO"
        a.resumo = (f"{w.novos} novos contra {base_n:.0f} ({rel_n:+.0f}%), mas quem voltou ficou parecido ({w.voltaram} contra {base_v:.0f}): o denominador inflou sem ninguem voltar a mais. "
                    "Confira duplicatas na bronze e a regra de pessoa da silver")
    else:
        a.diagnostico = "PICO_DE_USO"
        a.resumo = (f"novos ({w.novos} contra {base_n:.0f}) e quem voltou ({w.voltaram} contra {base_v:.0f}) subiram juntos: parece uso real (campanha, lancamento). "
                    "Provavel alarme falso; confirme com o produto")
    return a


# ------------------------------------------------------------------ leitura do banco
def series_da_gold(dw) -> dict[str, list[Semana]]:
    saida: dict[str, list[Semana]] = {}
    for pais, semana, novos, el, v in dw.execute("SELECT pais, semana::text, novos, elegiveis, voltaram_7d FROM gold.agg_retorno_semana ORDER BY pais, semana").fetchall():
        saida.setdefault(pais, []).append(Semana(semana, novos, el, v))
    return saida


# Por pais e semana: quantos "novos" e quantos deles usam um endereco que ja aparecia com OUTRA pessoa antes da primeira vez dela.
# Usa a bronze (o endereco nao vai para a silver): une pela conversa (hash + horario).
SQL_ENDERECO = """
WITH conv AS (
  SELECT c.pais, c.usuario_id, b.hashed_ip, c.inicio_utc
  FROM silver.fato_conversa c JOIN bronze.wildchat b ON b.conversation_hash = c.conversation_hash AND b.primeira_resposta_ts = c.inicio_utc
  WHERE b.hashed_ip IS NOT NULL),
ip1 AS (SELECT pais, hashed_ip, min(inicio_utc) AS primeiro FROM conv GROUP BY 1, 2),
p1 AS (SELECT DISTINCT ON (pais, usuario_id) pais, usuario_id, hashed_ip FROM conv ORDER BY pais, usuario_id, inicio_utc)
SELECT u.pais, u.semana::text, count(*), count(*) FILTER (WHERE ip1.primeiro < u.primeira_vez_utc)
FROM silver.fato_usuario u JOIN p1 ON p1.pais = u.pais AND p1.usuario_id = u.usuario_id JOIN ip1 ON ip1.pais = p1.pais AND ip1.hashed_ip = p1.hashed_ip
GROUP BY 1, 2"""


def enderecos_todos(dw) -> dict[str, dict]:
    saida: dict[str, dict] = {}
    with dw.transaction():
        dw.execute("SET LOCAL max_parallel_workers_per_gather = 0")      # consulta paralela usa /dev/shm, que no container tem so 64 MB (DiskFull)
        linhas = dw.execute(SQL_ENDERECO).fetchall()
    for pais, semana, n, jv in linhas:
        saida.setdefault(pais, {})[semana] = (n, jv)
    return saida


def analisar(dw) -> list[AlertaSemanal]:
    series, end = series_da_gold(dw), enderecos_todos(dw)
    return [diagnosticar(pais, w, ant, end.get(pais)) for pais, w, ant in sinalizadas(series, end)]


# ------------------------------------------------------------------ dentro da carga
def carga_anterior_com_verificacao(ops, exec_id: int) -> int | None:
    r = ops.execute("""SELECT max(e.id) FROM ops.etl_execucao e WHERE e.id < %s AND e.status IN ('ok', 'alerta')
                         AND EXISTS (SELECT 1 FROM ops.qa_resultado q WHERE q.execucao_id = e.id AND q.transicao = 'anomalia_semanal')""", (exec_id,)).fetchone()
    return r[0] if r else None


def verificar(ops, dw, exec_id: int) -> list[Resultado]:
    """Aponta as semanas com pico que sao NOVAS desde a carga anterior; grava todas em auditoria.anomalia_semanal."""
    nome = ("Alerta semanal: nenhuma semana teve pico de novos, salto da taxa ou de 'novos' com endereco ja conhecido que seja novo em relacao a carga anterior, "
            "comparada com as 6 semanas anteriores")
    alertas = analisar(dw)
    ref = carga_anterior_com_verificacao(ops, exec_id)
    conhecidos = set() if ref is None else {tuple(r) for r in ops.execute(
        "SELECT pais, semana::text, diagnostico FROM auditoria.anomalia_semanal WHERE execucao_id = %s", (ref,)).fetchall()}
    ops.execute("DELETE FROM auditoria.anomalia_semanal WHERE execucao_id = %s", (exec_id,))
    for a in alertas:
        ops.execute("""INSERT INTO auditoria.anomalia_semanal (execucao_id, pais, semana, diagnostico, camada, novos, novos_base, voltaram, voltaram_base, taxa, taxa_base,
                                                               pct_endereco, pct_endereco_base, resumo, nova)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (exec_id, a.pais, a.semana, a.diagnostico, a.camada, a.novos, a.novos_base, a.voltaram, a.voltaram_base, a.taxa, a.taxa_base,
                     a.pct_endereco, a.pct_endereco_base, a.resumo, ref is not None and a.chave not in conhecidos))
    if ref is None:
        print(f"[anomalia-semanal] primeira verificacao: {len(alertas)} semana(s) com pico registrada(s) como linha de base (nada a comparar ainda)", flush=True)
        return [Resultado("anomalia_semanal", nome, "linha de base", "linha de base", True)]
    novos = [a for a in alertas if a.chave not in conhecidos]
    for a in novos:
        print(f"[anomalia-semanal] {a.pais}, semana de {a.semana}: {a.diagnostico} (camada: {a.camada}). {a.resumo}", flush=True)
    if len(alertas) > len(novos):
        print(f"[anomalia-semanal] {len(alertas) - len(novos)} semana(s) com pico ja conhecida(s) da carga {ref} (veja auditoria.anomalia_semanal)", flush=True)
    return [Resultado("anomalia_semanal", f"{nome} (carga anterior: {ref})", "0", str(len(novos)), not novos)]


def main() -> int:
    """Lista, no banco atual, todas as semanas com pico e o diagnostico de cada uma (nao grava nada)."""
    from . import banco
    dw = banco.conectar(autocommit=True)
    alertas = analisar(dw)
    print(f"{len(alertas)} semana(s) com pico ou salto (comparadas com as 6 semanas anteriores):\n")
    for a in alertas:
        print(f"{a.pais:<18} semana de {a.semana}  {a.diagnostico:<20} camada: {a.camada:<17} novos {a.novos} (base {a.novos_base:.0f}), voltaram {a.voltaram} (base {a.voltaram_base:.0f})")
        print(f"    {a.resumo}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
