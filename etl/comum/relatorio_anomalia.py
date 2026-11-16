"""RELATORIO EM PDF DA ANOMALIA: so existe quando o detector achou algo (a carga ficou retida ou foi publicada com aprovacao).
Carga normal, sem anomalia, nao gera arquivo. O PDF diz: o que aconteceu, em que camada provavelmente comecou, o que mudou (antes e agora),
uma amostra das pessoas envolvidas (codigos anonimos: nao ha nome, e-mail nem IP) e o que fazer em seguida.
Sai em exports/relatorio_anomalia_carga_<id>.pdf (na pasta montada em /saida)."""
import json
import os
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PASTA = os.environ.get("SAIDA_RELATORIO", "/saida")
AZUL, CINZA, VERMELHO, AMARELO = colors.HexColor("#1f4e79"), colors.HexColor("#5f6368"), colors.HexColor("#b3261e"), colors.HexColor("#fff4cc")
CAMADA = {"BRONZE": "BRONZE: o dado de entrada mudou", "SILVER": "SILVER: limpeza e regras", "GOLD": "GOLD: agregação",
          "TRANSFORMACAO": "TRANSFORMAÇÃO: regra, parâmetro ou código mudou", "SEM_CAUSA": "sem causa técnica aparente (pode ser comportamento real)",
          "SILVER_OU_BRONZE": "SILVER ou BRONZE: pessoa ou entrada"}
DIAGNOSTICO = {"PESSOA_DIVIDIDA": "a mesma pessoa foi contada várias vezes", "DENOMINADOR_INFLADO": "o número de pessoas elegíveis inflou",
               "PICO_DE_USO": "pico de uso da semana", "QUEDA_DE_NOVOS": "queda de pessoas novas", "TAXA_SEMANAL": "a taxa da semana saltou"}


def _est():
    s = getSampleStyleSheet()
    return {"t": ParagraphStyle("t", parent=s["Title"], fontSize=19, textColor=AZUL, alignment=0, spaceAfter=4),
            "h": ParagraphStyle("h", parent=s["Heading2"], fontSize=12, textColor=AZUL, spaceBefore=10, spaceAfter=3),
            "p": ParagraphStyle("p", parent=s["BodyText"], fontSize=9.5, leading=13),
            "peq": ParagraphStyle("peq", parent=s["BodyText"], fontSize=8, leading=10.5, textColor=CINZA),
            "cel": ParagraphStyle("cel", parent=s["BodyText"], fontSize=8.5, leading=10.5)}


def _p(texto, estilo):
    return Paragraph(escape(str(texto)), estilo)


def _tabela(cabecalho, linhas, larguras, est):
    dados = [[_p(c, est["cel"]) for c in cabecalho]] + [[_p(c, est["cel"]) for c in l] for l in linhas]
    t = Table(dados, colWidths=[w * cm for w in larguras], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7ccd1")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _pct(v):
    return "-" if v is None else f"{float(v) * 100:.1f}%"


def _pessoas(dw, pais: str, semana=None) -> list:
    """Amostra das pessoas mais ativas do pais (ou dos que chegaram naquela semana), na carga que acabou de ser construida. So codigo anonimo."""
    filtro, args = ("AND semana = %s", (pais, semana)) if semana else ("", (pais,))
    return dw.execute(f"""SELECT usuario_id, convs_total, voltou_7d, navegador, sistema FROM silver.fato_usuario
                          WHERE pais = %s {filtro} ORDER BY convs_total DESC, usuario_id LIMIT 8""", args).fetchall()


def _tabela_pessoas(linhas, est):
    return _tabela(["Pessoa (código anônimo)", "Conversas", "Voltou em 7 dias", "Navegador / sistema"],
                   [[u, c, "sim" if v else "não", f"{n}/{s}"] for u, c, v, n, s in linhas], [5.2, 2.4, 3.4, 5.9], est)


def gerar(ops, dw, exec_id: int, situacao: str, pasta: str | None = None) -> str | None:
    """Gera o PDF desta carga. Devolve o caminho, ou None se nao houve anomalia (nesse caso nao cria arquivo)."""
    paises = ops.execute("""SELECT pais, tipo, origem, taxa_referencia, taxa_atual, elegiveis_referencia, elegiveis_atual, z, resumo, sinais
                            FROM auditoria.anomalia WHERE execucao_id = %s ORDER BY pais""", (exec_id,)).fetchall()
    semanas = ops.execute("""SELECT pais, semana, diagnostico, camada, novos, novos_base, voltaram, voltaram_base, taxa, taxa_base, pct_endereco, pct_endereco_base, resumo
                             FROM auditoria.anomalia_semanal WHERE execucao_id = %s AND nova ORDER BY (pais <> 'Brazil'), pais, semana""", (exec_id,)).fetchall()
    if not paises and not semanas:
        return None
    pasta = pasta or PASTA
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"relatorio_anomalia_carga_{exec_id}.pdf")
    est = _est()
    corpo = [Paragraph(f"Relatório de anomalia: carga {exec_id}", est["t"]),
             _p(f"Gerado em {datetime.now():%d/%m/%Y %H:%M}. Situação: {situacao}. {len(paises)} anomalia(s) de taxa ou de entrada e {len(semanas)} alerta(s) semanal(is).", est["p"]),
             Spacer(1, 6),
             _p("Este arquivo só é criado quando o detector encontra algo. As pessoas listadas são uma amostra das mais ativas para você olhar o dado, "
                "não são culpadas nem a causa: o código é anônimo e não leva nome, e-mail nem IP.", est["peq"])]

    for pais, tipo, origem, ref, atual, n_ref, n_atual, z, resumo, sinais in paises:
        bloco = [Paragraph(f"País {pais}: retorno em 7 dias {_pct(ref)} para {_pct(atual)}", est["h"]),
                 _p(f"Camada provável: {CAMADA.get(origem, origem)}. Pessoas elegíveis: {n_ref} para {n_atual}"
                    + ("" if z is None else f"; z = {float(z):.1f}") + ".", est["p"]),
                 _p(resumo, est["p"])]
        suspeitos = [s for s in (sinais if isinstance(sinais, list) else json.loads(sinais or "[]")) if s.get("suspeito")]
        if suspeitos:
            bloco += [Paragraph("Sinais que mudaram de padrão (antes e agora)", est["h"]),
                      _tabela(["Camada", "Etapa", "Antes", "Agora"], [[s["camada"], s["etapa"], s["antes"], s["agora"]] for s in suspeitos], [2.2, 9.2, 2.8, 2.7], est)]
        pessoas = _pessoas(dw, pais)
        if pessoas:
            bloco += [Paragraph("Amostra de pessoas do país (as mais ativas)", est["h"]), _tabela_pessoas(pessoas, est)]
        corpo.append(KeepTogether(bloco))

    for pais, semana, diag, camada, novos, novos_base, voltaram, voltaram_base, taxa, taxa_base, pct_e, pct_e_base, resumo in semanas:
        bloco = [Paragraph(f"Semana de {semana} ({pais}): {DIAGNOSTICO.get(diag, diag)}", est["h"]),
                 _p(f"Camada provável: {CAMADA.get(camada, camada)}. Pessoas novas: {novos} (normal: cerca de {float(novos_base):.0f}); "
                    f"voltaram: {voltaram} (normal: cerca de {float(voltaram_base):.0f}); retorno {_pct(taxa)} (normal {_pct(taxa_base)})"
                    + ("" if pct_e is None else f"; novas com endereço já conhecido: {_pct(pct_e)} (normal {_pct(pct_e_base)})") + ".", est["p"]),
                 _p(resumo, est["p"])]
        pessoas = _pessoas(dw, pais, semana)
        if pessoas:
            bloco += [Paragraph("Amostra de pessoas que chegaram nessa semana", est["h"]), _tabela_pessoas(pessoas, est)]
        corpo.append(KeepTogether(bloco))

    proximo = ("<b>Próximo passo.</b> Para ver o que mudou: <font face='Courier'>docker compose --profile operacao run --rm investigar-anomalias</font>. "
               "Se for real e você aprova: <font face='Courier'>docker compose run --rm etl python main.py --aprovar-anomalias</font>. "
               "Se for defeito: corrija a causa e rode <font face='Courier'>docker compose run --rm etl python main.py --recarregar</font>.")
    t = Table([[Paragraph(proximo, est["p"])]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMARELO), ("BOX", (0, 0), (-1, -1), 0.8, VERMELHO), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    corpo += [Spacer(1, 10), t]
    SimpleDocTemplate(caminho, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                      title=f"Relatório de anomalia, carga {exec_id}").build(corpo)
    return caminho
