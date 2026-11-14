"""Gera exports/fluxo_dos_dados.html: uma pagina unica que mostra o caminho do dado (arquivos -> bronze -> silver -> gold -> API) com
as contagens de cada etapa e o resultado de TODAS as conferencias (camadas entre si e API x gold). Verde = bate; vermelho = divergencia.

Uso: docker compose --profile test run --rm relatorio-fluxo   (grava em ./exports/fluxo_dos_dados.html)"""
import html
import os
import sys
from datetime import datetime

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app import seguranca
from app.main import app
from tests import conciliacao as cc

SAIDA = os.environ.get("SAIDA", "/saida/fluxo_dos_dados.html")
ROT = {"paises": "Lista de países", "resumo": "Resumo (números do topo)", "coortes": "Semanas", "meses": "Meses", "fatores": "O que faz voltar",
       "comparacao": "Comparação entre países", "curva": "Curva de retorno", "estratos": "Diferença simples por estrato", "modelos": "Versões do modelo",
       "concentracao": "Concentração de uso", "uso_hora": "Uso por hora", "uso_diario": "Uso por dia", "efeitos": "Efeitos (AIPW)",
       "decomposicao": "Por que o retorno mudou", "catalogo": "Catálogo de indicadores", "qualidade": "Painel de qualidade", "seguranca": "Acesso e segurança",
       "camadas": "Camadas entre si"}


def n(x):
    return f"{int(x):,}".replace(",", ".") if x is not None else "-"


def esc(x):
    return html.escape(str(x))


def main() -> int:
    with psycopg.connect(os.environ["DATABASE_URL_ETL"], row_factory=dict_row, autocommit=True) as db:
        um = lambda sql: list(db.execute(sql).fetchone().values())[0]
        with TestClient(app) as client, TestClient(app) as anon:
            client.cookies.set(seguranca.COOKIE, seguranca.criar_token("relatorio@local", "Relatorio"))
            paises = cc.paises_de_teste(db)
            checks = cc.camadas(db) + cc.Conciliador(client, db).todos(paises, anon)
            ex = db.execute("SELECT id, status, iniciado_em, versao_codigo FROM ops.etl_execucao ORDER BY id DESC LIMIT 1").fetchone()
            qa = db.execute("SELECT transicao, count(*) n, count(*) FILTER (WHERE passou) ok FROM ops.qa_resultado WHERE execucao_id = %s GROUP BY 1 ORDER BY 1", (ex["id"],)).fetchall()
            deriva = db.execute("SELECT count(*) FROM auditoria.mudancas_entre_cargas").fetchone()["count"]
            arq = db.execute("SELECT arquivo, linhas, left(sha256, 12) h FROM ops.bronze_lote WHERE execucao_id = %s ORDER BY arquivo", (ex["id"],)).fetchall()
            etapas = [
                ("Arquivos da semente", sum(a["linhas"] for a in arq), "linhas nos 2 arquivos Parquet"),
                ("Bronze", um("SELECT count(*) FROM bronze.wildchat"), "conversas, como vieram"),
                ("Silver (conversas)", um("SELECT count(*) FROM silver.fato_conversa"), f"depois de excluir {n(um('SELECT count(*) FROM auditoria.registro_excluido'))}"),
                ("Silver (pessoas)", um("SELECT count(*) FROM silver.fato_usuario"), "pessoas (endereço + navegador)"),
                ("Elegíveis", um("SELECT count(*) FROM silver.fato_usuario WHERE elegivel"), "pessoas com 7 dias de janela"),
                ("Voltaram em 7 dias", um("SELECT count(*) FROM silver.fato_usuario WHERE elegivel AND voltou_7d"), "entre as elegíveis"),
            ]
            br = client.get("/api/retencao/resumo", params={"pais": "Brazil"}).json()
            gp = db.execute("SELECT usuarios_elegiveis e, voltaram_7d v FROM gold.pais WHERE pais = 'Brazil'").fetchone()
            sb = db.execute("SELECT count(*) FILTER (WHERE elegivel) e, count(*) FILTER (WHERE elegivel AND voltou_7d) v FROM silver.fato_usuario WHERE pais = 'Brazil'").fetchone()
    ok = sum(c.ok for c in checks)
    ruins = [c for c in checks if not c.ok]
    por: dict[str, list] = {}
    for c in checks:
        por.setdefault(c.grupo, []).append(c)
    cor = "#0a7d33" if not ruins else "#b3261e"
    h = [f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fluxo dos dados</title>
<style>:root{{--bg:#fff;--fg:#1c1b1f;--mut:#5f6368;--card:#f6f7f9;--bd:#dfe1e5;--ok:#0a7d33;--bad:#b3261e}}
@media(prefers-color-scheme:dark){{:root{{--bg:#121316;--fg:#e8e8ea;--mut:#a0a3a8;--card:#1c1e22;--bd:#33363b;--ok:#4cc27a;--bad:#ff8a80}}}}
body{{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px;max-width:1100px;margin-inline:auto}}
h1{{font-size:22px;margin:.2em 0}}h2{{font-size:17px;margin:1.6em 0 .4em}}.mut{{color:var(--mut)}}
.flow{{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch}}.box{{flex:1 1 150px;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:10px}}
.box b{{display:block;font-size:20px}}.seta{{align-self:center;color:var(--mut)}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border-bottom:1px solid var(--bd);padding:6px 8px;text-align:left;vertical-align:top}}
.ok{{color:var(--ok);font-weight:600}}.bad{{color:var(--bad);font-weight:600}}.sel{{display:inline-block;padding:4px 12px;border-radius:99px;color:#fff;background:{cor};font-weight:600}}
details{{margin:4px 0}}summary{{cursor:pointer}}code{{font-size:13px}}</style></head><body>
<h1>Fluxo dos dados, da semente à tela</h1>
<p class="mut">Gerado em {datetime.now():%d/%m/%Y %H:%M} · carga nº {ex['id']} ({esc(ex['status'])}, código {esc(ex['versao_codigo'])}) · países testados na API: {esc(', '.join(paises))}</p>
<p><span class="sel">{ok} de {len(checks)} conferências batem{'' if not ruins else f' · {len(ruins)} DIVERGEM'}</span> · mudanças desde a carga anterior: <b>{deriva}</b></p>
<h2>1. O caminho e as contagens</h2><div class="flow">"""]
    for i, (t, v, d) in enumerate(etapas):
        h.append(f'{"<div class=seta>→</div>" if i else ""}<div class="box">{esc(t)}<b>{n(v)}</b><span class="mut">{esc(d)}</span></div>')
    h.append("</div><p class=mut>Os arquivos viram a bronze sem perder linha; a silver exclui só o que está registrado em <code>auditoria.registro_excluido</code>; "
             "a gold resume a silver; a API calcula taxa e margem de erro em cima da gold; a tela só mostra o que a API devolve.</p>")
    h.append("<h2>2. O número principal, passo a passo (Brasil)</h2><table><tr><th>Onde</th><th>Elegíveis</th><th>Voltaram</th><th>Taxa</th></tr>")
    for nome, e, v in (("Silver (conta direto nas pessoas)", sb["e"], sb["v"]), ("Gold (gold.pais)", gp["e"], gp["v"]), ("API (/api/retencao/resumo)", br["elegiveis"], br["voltaram_7d"])):
        h.append(f"<tr><td>{nome}</td><td>{n(e)}</td><td>{n(v)}</td><td>{v / e * 100:.2f}%</td></tr>")
    h.append(f"</table><p class=mut>Margem de erro (95%) mostrada na tela: {br['ic_lo'] * 100:.2f}% a {br['ic_hi'] * 100:.2f}%. Recalculada em Python: "
             f"{cc.wilson(gp['v'], gp['e'])[0] * 100:.2f}% a {cc.wilson(gp['v'], gp['e'])[1] * 100:.2f}%.</p>")
    h.append("<h2>3. Arquivos de entrada</h2><table><tr><th>Arquivo</th><th>Linhas</th><th>sha256 (início)</th></tr>" +
             "".join(f"<tr><td>{esc(a['arquivo'])}</td><td>{n(a['linhas'])}</td><td><code>{esc(a['h'])}</code></td></tr>" for a in arq) + "</table>")
    h.append("<h2>4. Conferências do ETL nesta carga</h2><table><tr><th>Transição</th><th>Passaram</th></tr>" +
             "".join(f"<tr><td>{esc(q['transicao'])}</td><td class={'ok' if q['n'] == q['ok'] else 'bad'}>{q['ok']} de {q['n']}</td></tr>" for q in qa) + "</table>")
    h.append("<h2>5. Camadas entre si e API × gold (clique para abrir)</h2>")
    for g in ["camadas"] + [k for k in por if k != "camadas"]:
        cs = por.get(g, [])
        bons = sum(c.ok for c in cs)
        h.append(f"<details {'open' if bons != len(cs) else ''}><summary><b>{esc(ROT.get(g, g))}</b> · <span class={'ok' if bons == len(cs) else 'bad'}>{bons} de {len(cs)}</span></summary><table>")
        for c in cs:
            h.append(f"<tr><td class={'ok' if c.ok else 'bad'}>{'✔' if c.ok else '✘'}</td><td>{esc(c.pais or '')}</td><td>{esc(c.descricao)}</td>"
                     f"<td><code>{esc(c.esperado)}</code> × <code>{esc(c.obtido)}</code> {esc(c.detalhe)}</td></tr>")
        h.append("</table></details>")
    h.append("<h2>Como ler</h2><p>“Esperado” é o que a gold (ou outra tabela, ou o cálculo em Python) diz; “obtido” é o que a API devolve. "
             "Nas linhas “divergências”, o esperado é sempre 0.</p></body></html>")
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("".join(h))
    print(f"{ok}/{len(checks)} conferencias batem; relatorio em {SAIDA}")
    return 1 if ruins else 0


if __name__ == "__main__":
    sys.exit(main())
