"""Sensibilidade das DEFINICOES: quanto o retorno em 7 dias do Brasil muda se uma premissa estiver errada (PDF 2.3 e 3.1).

Refaz o indicador (usuario, sessao, primeira experiencia, retorno, elegibilidade) direto da bronze, variando UMA premissa por vez,
e compara com a definicao adotada (BDR-001). Reproduzivel: com o `docker compose up` ativo,
    python analise/05_sensibilidade_definicoes.py
Grava docs/SENSIBILIDADE.md. A variante "adotada" TEM de bater com o dashboard (2.234 elegiveis, 530 voltaram); se nao bater, o script falha.
"""
import math
import pathlib
import sys

import psycopg

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "etl"))
from pipeline.definicoes import GAP_SESSAO_MIN, JANELA_RETORNO_DIAS, LAVAGEM_DIAS, UA_NORM_SQL  # noqa: E402

URL = "postgresql://etl:etl@localhost:5433/retencao"
PAIS = "Brazil"

# (grupo, rotulo, parametros). Cada variante muda UMA coisa em relacao a "adotada".
ADOTADA = dict(usuario="ip_ua_norm", gap=GAP_SESSAO_MIN, lavagem=LAVAGEM_DIAS, janela=JANELA_RETORNO_DIAS, inicio="primeira_resposta",
               regra="sessao", sem_top=0)
VARIANTES = [
    ("Referência", "Definição adotada (IP + navegador/sistema, sessão de 30 min, janela de 7 dias)", {}),
    ("Quem é o usuário", "Só o IP", dict(usuario="ip")),
    ("Quem é o usuário", "IP + user-agent completo (com a versão do navegador)", dict(usuario="ip_ua_completo")),
    ("Gap da sessão", "15 minutos", dict(gap=15)),
    ("Gap da sessão", "60 minutos", dict(gap=60)),
    ("Gap da sessão", "120 minutos", dict(gap=120)),
    ("Período de lavagem", "14 dias", dict(lavagem=14)),
    ("Período de lavagem", "60 dias", dict(lavagem=60)),
    ("Janela de retorno", "3 dias", dict(janela=3)),
    ("Janela de retorno", "14 dias", dict(janela=14)),
    ("Início da conversa", "Horário do último turno (campo timestamp)", dict(inicio="ultimo_turno")),
    ("Regra de retorno", "Qualquer conversa 1 h depois da primeira (sem sessão; regra do incidente)", dict(regra="hora")),
    ("Usuários extremos", "Sem o usuário mais ativo", dict(sem_top=1)),
    ("Usuários extremos", "Sem os 10 usuários mais ativos", dict(sem_top=10)),
]

SQL = """
WITH base AS (
  SELECT DISTINCT ON (conversation_hash, hashed_ip, ini) hashed_ip, ua, ini, fim FROM (
    SELECT conversation_hash, hashed_ip, header->>'user-agent' AS ua, {ini} AS ini, "timestamp" AS fim
    FROM bronze.wildchat WHERE country = %(pais)s AND hashed_ip IS NOT NULL) x
  WHERE ini IS NOT NULL ORDER BY conversation_hash, hashed_ip, ini, fim),
k AS (
  SELECT *, {chave} AS uk FROM (SELECT *, {ua_norm} AS ua_norm FROM base) b),
ativos AS (SELECT uk FROM k GROUP BY uk ORDER BY count(*) DESC, uk LIMIT %(sem_top)s),
k2 AS (SELECT * FROM k WHERE uk NOT IN (SELECT uk FROM ativos)),
o AS (
  SELECT *, CASE WHEN lag(fim) OVER w IS NULL OR ini - lag(fim) OVER w > make_interval(mins => %(gap)s) THEN 1 ELSE 0 END AS nova
  FROM k2 WINDOW w AS (PARTITION BY uk ORDER BY ini, fim)),
s AS (SELECT *, sum(nova) OVER (PARTITION BY uk ORDER BY ini, fim) AS sess, min(ini) OVER (PARTITION BY uk) AS primeira FROM o),
u AS (
  SELECT uk, min(primeira) AS primeira, {voltou} AS voltou FROM s GROUP BY uk),
lim AS (SELECT min(ini) AS mn, max(ini) AS mx FROM k2)
SELECT count(*), count(*) FILTER (WHERE el), count(*) FILTER (WHERE el AND voltou)
FROM (SELECT u.*, (primeira >= mn + make_interval(days => %(lavagem)s) AND primeira <= mx - make_interval(days => %(janela)s)) AS el
      FROM u CROSS JOIN lim) z
"""

CHAVES = {
    "ip": "hashed_ip",
    "ip_ua_norm": "hashed_ip || '|' || ua_norm",
    "ip_ua_completo": "hashed_ip || '|' || coalesce(ua, '')",
}
VOLTOU = {
    "sessao": "coalesce(bool_or(sess > 1 AND ini <= primeira + make_interval(days => %(janela)s)), false)",
    "hora": "coalesce(bool_or(ini > primeira + interval '1 hour' AND ini <= primeira + make_interval(days => %(janela)s)), false)",
}
INICIO = {"primeira_resposta": "primeira_resposta_ts", "ultimo_turno": '"timestamp"'}


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = x / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centro - meia, centro + meia


def rodar(cur, **mudancas) -> dict:
    p = {**ADOTADA, **mudancas}
    # os '%' do UA_NORM_SQL (ILIKE '%Edg/%') precisam ser escapados, porque a consulta usa parametros nomeados (%(nome)s)
    sql = SQL.format(ini=INICIO[p["inicio"]], chave=CHAVES[p["usuario"]], voltou=VOLTOU[p["regra"]], ua_norm=UA_NORM_SQL.replace("%", "%%"))
    cur.execute(sql, dict(pais=PAIS, gap=p["gap"], lavagem=p["lavagem"], janela=p["janela"], sem_top=p["sem_top"]))
    usuarios, elegiveis, voltaram = cur.fetchone()
    lo, hi = wilson(voltaram, elegiveis)
    return dict(usuarios=usuarios, elegiveis=elegiveis, voltaram=voltaram, taxa=voltaram / elegiveis if elegiveis else math.nan, lo=lo, hi=hi)


def main() -> int:
    linhas = []
    with psycopg.connect(URL) as dw, dw.cursor() as cur:
        for grupo, rotulo, mud in VARIANTES:
            linhas.append((grupo, rotulo, rodar(cur, **mud)))
    base = linhas[0][2]
    if (base["elegiveis"], base["voltaram"]) != (2234, 530):
        print(f"ERRO: a definicao adotada nao bate com o dashboard (esperado 2.234 / 530, obtido {base['elegiveis']} / {base['voltaram']})")
        return 1
    meia_base = (base["hi"] - base["lo"]) / 2 * 100

    def pct(v): return f"{v * 100:.1f}%".replace(".", ",")
    def mil(v): return f"{v:,}".replace(",", ".")
    def pp(v): return f"{v:+.1f} pp".replace(".", ",").replace("-", "−")
    saida = ["# Sensibilidade das definições: quanto o retorno do Brasil muda se uma premissa estiver errada", "",
             "Gerado por `analise/05_sensibilidade_definicoes.py` (reproduzível: com o `docker compose up` ativo, rode o script). Cada linha refaz o indicador "
             "direto da bronze mudando **uma** premissa por vez; a primeira linha é a definição adotada e **bate com o dashboard** "
             "(2.234 elegíveis, 530 voltaram, 23,7%).", "",
             f"Leitura: a incerteza estatística da definição adotada é de **±{str(round(meia_base, 1)).replace(".", ",")} pp** (IC 95%). Uma variante que muda o retorno por menos que isso "
             "não altera a conclusão; mais que isso, **muda a leitura do número**.", "",
             "| Premissa | Variante | Usuários | Elegíveis | Voltaram | Retorno (IC 95%) | Diferença | Leitura |", "|---|---|---:|---:|---:|---|---:|---|"]
    for grupo, rotulo, r in linhas:
        dif = (r["taxa"] - base["taxa"]) * 100
        leitura = "referência" if r is base else ("dentro da incerteza" if abs(dif) <= meia_base else "**muda a leitura**")
        saida.append(f"| {grupo} | {rotulo} | {mil(r['usuarios'])} | {mil(r['elegiveis'])} | {mil(r['voltaram'])} | {pct(r['taxa'])} ({pct(r['lo'])} a {pct(r['hi'])}) | "
                     f"{'-' if r is base else pp(dif)} | {leitura} |")
    por_grupo = {}
    for grupo, _, r in linhas:
        if grupo != "Referência":
            por_grupo.setdefault(grupo, []).append(r["taxa"] * 100)
    ordem = sorted(por_grupo.items(), key=lambda kv: -(max(kv[1] + [base["taxa"] * 100]) - min(kv[1] + [base["taxa"] * 100])))
    saida += ["", "## Quais premissas mais mexem no número", "", "Faixa do retorno ao variar cada premissa (a adotada incluída), da mais para a menos sensível:", ""]
    for grupo, taxas in ordem:
        v = taxas + [base["taxa"] * 100]
        saida.append(f"- **{grupo}:** de {str(round(min(v), 1)).replace('.', ',')}% a {str(round(max(v), 1)).replace('.', ',')}% "
                     f"(amplitude de {str(round(max(v) - min(v), 1)).replace('.', ',')} pp)")
    saida += ["", "## Como ler", "",
              "- **Só o IP** junta quem divide a rede (celular, escola, CGNAT) e reduz o número de usuários; **user-agent completo** separa quem atualiza o navegador "
              "(é a causa do incidente da seção 4.2). A definição adotada fica no meio: IP + família do navegador + sistema, sem versão.",
              "- **Gap da sessão** e **lavagem** mudam quem conta como \"voltou\" e quem conta como \"novo\"; **janela** muda o que é \"voltar\" (é outro indicador, não um erro).",
              "- **Horário do último turno** e a **regra de 1 h** são as armadilhas do código do incidente; estão aqui para mostrar quanto elas custariam.",
              "- **Sem os usuários mais ativos** mostra se poucos usuários (como o IP com 1.557 conversas) puxam o número.", "",
              "Limite: a amostra é pequena (cerca de 2,2 mil elegíveis), então diferenças menores que a incerteza acima não são distinguíveis de ruído."]
    (RAIZ / "docs" / "SENSIBILIDADE.md").write_text("\n".join(saida) + "\n", encoding="utf-8")
    print("\n".join(saida))
    return 0


if __name__ == "__main__":
    sys.exit(main())
