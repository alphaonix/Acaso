"""Relatorio em PDF da simulacao de anomalias: uma pagina por cenario escolhido, em linguagem simples.
Cada pagina diz: onde o defeito COMECA, o que foi simulado, o que o sistema detectou (funil camada por camada), POR QUE aquilo pode ser uma
anomalia de verdade, POR QUE pode ser um alarme falso, o que conferir primeiro e o que o portao de qualidade tambem apontou."""
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from comum.anomalia import Sinal
from .catalogo import CAMADA_TITULO

AZUL, CINZA, VERDE, VERMELHO, AMARELO = colors.HexColor("#1f4e79"), colors.HexColor("#5f6368"), colors.HexColor("#0a7d33"), colors.HexColor("#b3261e"), colors.HexColor("#fff4cc")
COR_CAMADA = {"bronze": colors.HexColor("#8a5a00"), "silver": colors.HexColor("#4a5568"), "gold": colors.HexColor("#b08900"), "codigo": colors.HexColor("#6b2d8f"), "nenhuma": VERDE}
NOMES_ORIGEM = {"BRONZE": "BRONZE (o dado de entrada)", "SILVER": "SILVER (limpeza e regras)", "GOLD": "GOLD (agregação)", "TRANSFORMACAO": "TRANSFORMAÇÃO (o código mudou)",
                "SEM_CAUSA": "SEM CAUSA TÉCNICA APARENTE"}


def _estilos():
    s = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("t", parent=s["Title"], fontSize=20, textColor=AZUL, alignment=0, spaceAfter=6),
        "h1": ParagraphStyle("h1", parent=s["Heading1"], fontSize=15, textColor=AZUL, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=s["Heading2"], fontSize=11.5, textColor=AZUL, spaceBefore=9, spaceAfter=3),
        "p": ParagraphStyle("p", parent=s["BodyText"], fontSize=9.5, leading=13),
        "peq": ParagraphStyle("peq", parent=s["BodyText"], fontSize=8, leading=10.5, textColor=CINZA),
        "cel": ParagraphStyle("cel", parent=s["BodyText"], fontSize=8.5, leading=10.5),
        "celb": ParagraphStyle("celb", parent=s["BodyText"], fontSize=8.5, leading=10.5, textColor=colors.white),
        "lista": ParagraphStyle("l", parent=s["BodyText"], fontSize=9, leading=12, leftIndent=12, bulletIndent=2),
    }


def _p(texto, estilo):
    return Paragraph(escape(str(texto)), estilo)


def _caixa(texto, estilos, fundo, cor_borda):
    t = Table([[Paragraph(texto, estilos["p"])]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fundo), ("BOX", (0, 0), (-1, -1), 0.8, cor_borda), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _funil(achado, e):
    linhas = [[Paragraph("Camada", e["celb"]), Paragraph("Etapa", e["celb"]), Paragraph("Antes", e["celb"]), Paragraph("Agora", e["celb"]), Paragraph("Mudou?", e["celb"])]]
    estilo = [("BACKGROUND", (0, 0), (-1, 0), AZUL), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i, s in enumerate(achado["sinais"], start=1):
        sin = Sinal(s["camada"], s["etapa"], s["antes"], s["agora"], s.get("unidade", "n"), s["suspeito"])
        linhas.append([_p(s["camada"].upper(), e["cel"]), _p(s["etapa"], e["cel"]), _p(sin.formatar(sin.antes), e["cel"]), _p(sin.formatar(sin.agora), e["cel"]),
                       _p("SIM" if s["suspeito"] else "", e["cel"])])
        if s["suspeito"]:
            estilo += [("BACKGROUND", (0, i), (-1, i), AMARELO), ("TEXTCOLOR", (4, i), (4, i), VERMELHO)]
    t = Table(linhas, colWidths=[2 * cm, 8.2 * cm, 2.6 * cm, 2.6 * cm, 1.6 * cm], repeatRows=1)
    t.setStyle(TableStyle(estilo))
    return t


def _pagina_cenario(n, r, e):
    c, a = r["cenario"], r["achado"]
    cor = COR_CAMADA[c.camada]
    itens = [Paragraph(f"Cenário {n}: {escape(c.titulo)}", e["h1"])]
    faixa = Table([[Paragraph(f"O defeito começa em: {escape(CAMADA_TITULO[c.camada])}", e["celb"])]], colWidths=[17 * cm])
    faixa.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), cor), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    itens += [faixa, Spacer(1, 6), Paragraph("O que foi simulado", e["h2"]), _p(c.defeito, e["p"]), Paragraph("O que o sistema detectou", e["h2"])]
    if a:
        tipo = {"TAXA": "a taxa de retorno saltou", "ENTRADA": "a taxa quase não mudou, mas o dado de entrada mudou de padrão",
                "LIMPEZA": "a taxa quase não mudou, mas a limpeza da silver mudou de comportamento",
                "AGREGACAO": "a taxa quase não mudou, mas a gold não bate com a silver"}[a["tipo"]]
        itens.append(_p(f"Brasil: retorno em 7 dias de {a['taxa_ref'] * 100:.1f}% para {a['taxa_atual'] * 100:.1f}% (elegíveis {a['eleg_ref']} para {a['eleg_atual']}). "
                        f"Tipo de alerta: {tipo}.", e["p"]))
        itens.append(Spacer(1, 3))
        itens.append(_caixa(f"<b>Origem apontada pelo sistema:</b> {escape(NOMES_ORIGEM[a['origem']])}<br/>{escape(a['resumo'])}", e, colors.HexColor("#eef4fb"), AZUL))
        itens += [Spacer(1, 5), Paragraph("O funil, camada por camada (as linhas em amarelo mudaram)", e["h2"]), _funil(a, e)]
    else:
        itens.append(_p("Nenhum alerta para o Brasil.", e["p"]))
    if c.avaliar_semanal:
        itens += [Spacer(1, 5), Paragraph("O alerta semanal (compara cada semana com as 6 anteriores)", e["h2"])]
        if r["semanais"]:
            linhas = [[Paragraph(t, e["celb"]) for t in ("País", "Semana", "Diagnóstico", "Novos (normal)", "Voltaram (normal)", "Novos com endereço já visto")]]
            for s in r["semanais"][:8]:
                end = "-" if s["pct_endereco"] is None else f"{s['pct_endereco']:.0f}% (normal {s['pct_endereco_base']:.0f}%)"
                linhas.append([_p(s["pais"], e["cel"]), _p(s["semana"], e["cel"]), _p(s["diagnostico"], e["cel"]), _p(f"{s['novos']} ({s['novos_base']:.0f})", e["cel"]),
                               _p(f"{s['voltaram']} ({s['voltaram_base']:.0f})", e["cel"]), _p(end, e["cel"])])
            t = Table(linhas, colWidths=[2.6 * cm, 2.2 * cm, 3.6 * cm, 2.4 * cm, 2.6 * cm, 3.6 * cm], repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            itens += [t, Spacer(1, 3), _p(r["semanais"][0]["resumo"], e["peq"])]
        else:
            itens.append(_p("Nenhum alerta semanal novo em nenhum país.", e["p"]))
        esp_s = c.esperada_semanal or "nenhum alerta semanal"
        itens.append(_p(f"Esperado no alerta semanal: {esp_s}. {'CONFERE' if r['ok_semanal'] else 'NÃO CONFERE'}.", e["p"]))
    ok = r["ok"]
    esperado = NOMES_ORIGEM.get(c.esperada, "nenhum alerta") if c.esperada and c.esperada != "QUALQUER" else ("qualquer (o que vale é o alerta semanal)" if c.esperada == "QUALQUER" else "nenhum alerta")
    itens.append(Spacer(1, 5))
    itens.append(_caixa(f"<b>Resultado do teste:</b> esperado: {escape(esperado)}. Apontado: {escape(NOMES_ORIGEM.get(r['apontada'], r['apontada']))}. "
                        f"<font color='{'#0a7d33' if ok else '#b3261e'}'><b>{'CONFERE' if ok else 'NÃO CONFERE'}</b></font>",
                        e, colors.HexColor("#eef8f0") if ok else colors.HexColor("#fdeceb"), VERDE if ok else VERMELHO))
    itens += [Paragraph("Por que isto pode ser uma anomalia de verdade", e["h2"]), _p(c.anomalia_real, e["p"]),
              Paragraph("Por que isto pode ser um alarme falso", e["h2"]), _p(c.alarme_falso, e["p"]),
              Paragraph("Como saber qual dos dois é (confira nesta ordem)", e["h2"])]
    itens += [Paragraph(escape(v), e["lista"], bulletText="•") for v in c.verificar]
    if r["gate_falhas"]:
        itens.append(Paragraph(f"O portão de qualidade também reprovou {r['gate_n']} conferência(s) (algumas das primeiras)", e["h2"]))
        itens += [Paragraph(escape(f"{v}: esperado {x}, obtido {o}")[:230], e["lista"], bulletText="•") for v, x, o in r["gate_falhas"][:4]]
    return itens


def gerar(resultados: list[dict], caminho: str) -> None:
    e = _estilos()
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Relatório de simulação de anomalias", author="Retenção WildChat Brasil")
    ok_total = all(r["ok"] for r in resultados)
    h = [Paragraph("Relatório de simulação de anomalias", e["titulo"]),
         _p(f"Gerado em {datetime.now():%d/%m/%Y %H:%M}. Cenários simulados: {len(resultados)}. Resultado geral: "
            f"{'todos conferem' if ok_total else 'HÁ CENÁRIOS QUE NÃO CONFEREM'}.", e["peq"]), Spacer(1, 8),
         Paragraph("Para que serve este relatório", e["h2"]),
         _p("O sistema compara cada carga de dados com a anterior. Se a taxa de retorno de um país mudar demais, ou se o dado de entrada ou a limpeza mudarem de padrão, "
            "ele avisa e diz em qual camada a mudança começou. Aqui, defeitos foram plantados de propósito em camadas diferentes (num banco descartável, sem tocar nos dados "
            "reais) para provar que o aviso aparece e aponta a camada certa.", e["p"]),
         Paragraph("Como ler", e["h2"]),
         _p("As três camadas, em ordem: BRONZE é o dado como chegou da fonte; SILVER é o dado limpo, com as regras (quem é a pessoa, quem voltou, quem é elegível); "
            "GOLD é o resumo que o painel mostra. Um defeito que começa numa camada se espalha para as seguintes. Por isso o sistema procura a primeira camada que mudou. "
            "Em cada cenário há duas explicações: por que aquilo pode ser um problema de verdade e por que pode ser um alarme falso (uma mudança real do mundo, ou uma decisão "
            "intencional). O alerta é um aviso para investigar, nunca uma prova.", e["p"]),
         Paragraph("Resumo dos cenários", e["h2"])]
    linhas = [[Paragraph(t, e["celb"]) for t in ("Cenário", "Começa em", "Taxa do Brasil", "Origem apontada", "Resultado")]]
    for r in resultados:
        a, c = r["achado"], r["cenario"]
        linhas.append([_p(c.titulo, e["cel"]), _p(CAMADA_TITULO[c.camada].split(" (")[0], e["cel"]),
                       _p(f"{a['taxa_ref'] * 100:.1f}% para {a['taxa_atual'] * 100:.1f}%" if a else "sem alerta", e["cel"]),
                       _p(NOMES_ORIGEM.get(r["apontada"], r["apontada"]), e["cel"]), _p("CONFERE" if r["ok"] else "NÃO CONFERE", e["cel"])])
    t = Table(linhas, colWidths=[5.6 * cm, 2.4 * cm, 3 * cm, 4 * cm, 2 * cm], repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), AZUL), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i, r in enumerate(resultados, start=1):
        estilo.append(("TEXTCOLOR", (4, i), (4, i), VERDE if r["ok"] else VERMELHO))
    t.setStyle(TableStyle(estilo))
    h.append(t)
    for n, r in enumerate(resultados, start=1):
        h += [PageBreak()] + _pagina_cenario(n, r, e)
    h += [PageBreak(), Paragraph("Limites deste teste", e["h1"]),
          Paragraph("O alerta é uma pista, não uma prova: aponta a primeira camada em que alguma medida mudou. Um defeito numa coluna que não está entre as medidas acompanhadas "
                    "pode ser apontado como 'silver' ou como 'sem causa técnica'.", e["lista"], bulletText="•"),
          Paragraph("A comparação é sempre com a carga anterior, não com uma média histórica nem com a sazonalidade. Os limites (5 pontos percentuais, z de 4, 30% e 20%) são escolhas "
                    "e podem ser ajustados em etl/comum/anomalia.py.", e["lista"], bulletText="•"),
          Paragraph("Só a taxa de retorno em 7 dias, por país com 30 ou mais elegíveis, é avaliada. Os defeitos da gold só são vistos na tabela por país (gold.pais).", e["lista"], bulletText="•"),
          Paragraph("Na operação, a anomalia RETÉM a carga: nada é publicado e o painel continua com os números anteriores até alguém aprovar (--aprovar-anomalias); "
                    "o resultado fica em auditoria.anomalia. Nesta simulação a carga é desfeita de propósito. O portão de qualidade (conferências de conservação "
                    "entre camadas) também pode desfazer a carga.", e["lista"], bulletText="•")]

    def rodape(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(CINZA)
        canvas.drawString(2 * cm, 1 * cm, "Simulação de anomalias - dados de teste, banco descartável")
        canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(h, onFirstPage=rodape, onLaterPages=rodape)
