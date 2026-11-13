"""Figuras da análise exploratória (docs/EDA.md). Cada figura sustenta UMA conclusão (PDF 3.1: "mostre só os gráficos que levaram a uma conclusão").
Reprodutível, com o `docker compose up` ativo:   python analise/06_eda_figuras.py
Lê a silver (e, para o idioma do navegador, a bronze) do Brasil e grava docs/figuras/*.png. Não grava nada no banco.
"""
import math
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import psycopg

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "figuras"
SAIDA.mkdir(parents=True, exist_ok=True)
URL = "postgresql://etl:etl@localhost:5433/retencao"

ROXO, ROXO_ESC, AZUL, CINZA, VERM = "#a00bff", "#63079e", "#1f8fae", "#9a9aa8", "#c0262d"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "figure.dpi": 150,
                     "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "-"})


def wilson(x, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = x / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - m) * 100, (c + m) * 100


def consulta(cur, sql, params=None):
    cur.execute(sql, params)
    return cur.fetchall()


def salvar(fig, nome):
    fig.savefig(SAIDA / nome, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("gravada", nome)


def pontos_ic(ax, rotulos, voltaram, elegiveis, cores=None, referencia=None):
    """Taxa com IC 95% (Wilson) em pontos horizontais; n ao lado de cada rótulo."""
    y = np.arange(len(rotulos))[::-1]
    for i, (v, n) in enumerate(zip(voltaram, elegiveis)):
        lo, hi = wilson(v, n)
        taxa = 100 * v / n
        cor = (cores[i] if cores else ROXO)
        ax.plot([lo, hi], [y[i], y[i]], color=cor, lw=3, alpha=0.55, solid_capstyle="round")
        ax.plot(taxa, y[i], "o", color=cor, ms=8)
        ax.text(max(hi, taxa) + 1.2, y[i], f"{taxa:.1f}%  (n={n})", va="center", fontsize=9, color="#333")
    ax.set_yticks(y)
    ax.set_yticklabels(rotulos)
    ax.set_xlabel("retorno em 7 dias (%), com IC 95%")
    if referencia is not None:
        ax.axvline(referencia, color=CINZA, ls="--", lw=1)
    ax.set_xlim(0, max(55, ax.get_xlim()[1]))
    ax.grid(axis="y", visible=False)


with psycopg.connect(URL) as dw, dw.cursor() as cur:
    base = consulta(cur, "SELECT count(*) FILTER (WHERE voltou_7d), count(*) FROM silver.fato_usuario WHERE pais='Brazil' AND elegivel")[0]
    media = 100 * base[0] / base[1]

    # 1. o modelo muda com o calendário --------------------------------------------------------------
    mes = consulta(cur, """SELECT to_char(timezone('America/Sao_Paulo', inicio_utc), 'YYYY-MM') m, count(*),
                                  100.0*count(*) FILTER (WHERE modelo LIKE 'gpt-4%')/count(*)
                           FROM silver.fato_conversa WHERE pais='Brazil' GROUP BY 1 ORDER BY 1""")
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    x = np.arange(len(mes))
    ax.bar(x, [r[1] for r in mes], color=ROXO, alpha=0.85)
    ax.set_ylabel("conversas por mês")
    ax.set_xticks(x)
    ax.set_xticklabels([r[0][2:] for r in mes], rotation=45, ha="right")
    ax2 = ax.twinx()
    ax2.plot(x, [float(r[2]) for r in mes], color=AZUL, marker="o", lw=2)
    ax2.set_ylabel("% das conversas em GPT-4", color=AZUL)
    ax2.set_ylim(0, 100)
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax.set_title("O modelo mudou com o calendário: sem GPT-4 de jul a out/2023, mais de 90% em 2024")
    salvar(fig, "eda1_modelo_no_tempo.png")

    # 2. curva de retorno ----------------------------------------------------------------------------
    dias = consulta(cur, """
        WITH o AS (SELECT usuario_id, inicio_utc, fim_utc, CASE WHEN lag(fim_utc) OVER w IS NULL OR inicio_utc - lag(fim_utc) OVER w > interval '30 minutes' THEN 1 ELSE 0 END nova
                   FROM silver.fato_conversa WHERE pais='Brazil' WINDOW w AS (PARTITION BY usuario_id ORDER BY inicio_utc, fim_utc)),
        s AS (SELECT *, sum(nova) OVER (PARTITION BY usuario_id ORDER BY inicio_utc, fim_utc) sessao, min(inicio_utc) OVER (PARTITION BY usuario_id) primeira FROM o),
        seg AS (SELECT usuario_id, min(primeira) primeira, min(inicio_utc) FILTER (WHERE sessao = 2) segunda FROM s GROUP BY 1),
        lim AS (SELECT min(inicio_utc) mn, max(inicio_utc) mx FROM silver.fato_conversa WHERE pais='Brazil')
        SELECT extract(epoch FROM (segunda - primeira))/86400 FROM seg, lim WHERE primeira >= mn + interval '30 days' AND primeira <= mx - interval '30 days'""")
    d = np.array([float(r[0]) if r[0] is not None else np.inf for r in dias])
    grade = np.linspace(0, 30, 301)
    cum = [100 * np.mean(d <= g) for g in grade]
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    ax.plot(grade, cum, color=ROXO, lw=2.5)
    ax.axvline(7, color=CINZA, ls="--")
    ax.annotate(f"7 dias: {100 * np.mean(d <= 7):.1f}%", (7, 100 * np.mean(d <= 7)), xytext=(10, 12), textcoords="offset points", fontsize=10, fontweight="bold")
    ax.annotate(f"1 dia: {100 * np.mean(d <= 1):.1f}%", (1, 100 * np.mean(d <= 1)), xytext=(6, -22), textcoords="offset points", fontsize=9)
    ax.annotate(f"30 dias: {100 * np.mean(d <= 30):.1f}%", (30, 100 * np.mean(d <= 30)), xytext=(-70, 10), textcoords="offset points", fontsize=9)
    ax.set_xlabel("dias depois da primeira conversa")
    ax.set_ylabel("% que já voltou (2ª sessão)")
    ax.set_ylim(0, 35)
    ax.set_title(f"Quem volta, volta logo: {100 * np.mean(d <= 7) / np.mean(d <= 30):.0f}% dos retornos de 30 dias ocorrem em 7")
    salvar(fig, "eda2_curva_de_retorno.png")
    n_curva = len(d)

    # 3. concentração -------------------------------------------------------------------------------
    fx = consulta(cur, """WITH u AS (SELECT usuario_id, count(*) n FROM silver.fato_conversa WHERE pais='Brazil' GROUP BY 1)
        SELECT CASE WHEN n=1 THEN '1' WHEN n<=3 THEN '2 a 3' WHEN n<=10 THEN '4 a 10' WHEN n<=50 THEN '11 a 50' ELSE 'mais de 50' END,
               100.0*count(*)/sum(count(*)) OVER (), 100.0*sum(n)/sum(sum(n)) OVER (), count(*), min(n) FROM u GROUP BY 1 ORDER BY min(n)""")
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    x = np.arange(len(fx))
    ax.bar(x - 0.2, [float(r[1]) for r in fx], 0.4, color=AZUL, label="% das pessoas")
    ax.bar(x + 0.2, [float(r[2]) for r in fx], 0.4, color=ROXO, label="% das conversas")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r[0]}\n(n={r[3]})" for r in fx])
    ax.set_xlabel("conversas por pessoa")
    ax.legend(frameon=False)
    ax.set_title("Poucas pessoas fazem muito do volume: 20 pessoas geram 39% das conversas")
    salvar(fig, "eda3_concentracao.png")

    # 4. quando usam --------------------------------------------------------------------------------
    hd = consulta(cur, """SELECT extract(isodow FROM l)::int, extract(hour FROM l)::int, count(*) FROM
        (SELECT timezone('America/Sao_Paulo', inicio_utc) l FROM silver.fato_conversa WHERE pais='Brazil') x GROUP BY 1,2""")
    mat = np.zeros((7, 24))
    for dow, h, n in hd:
        mat[dow - 1, h] = n
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    im = ax.imshow(mat, aspect="auto", cmap="Purples")
    ax.set_yticks(range(7))
    ax.set_yticklabels(["seg", "ter", "qua", "qui", "sex", "sáb", "dom"])
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h}h" for h in range(0, 24, 2)])
    ax.add_patch(plt.Rectangle((8.5, -0.5), 9, 5, fill=False, ec=AZUL, lw=2))
    ax.text(13, -0.75, "expediente (seg a sex, 9h às 18h)", color=AZUL, fontsize=9, ha="center")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="conversas", shrink=0.8)
    exp = mat[:5, 9:18].sum() / mat.sum() * 100
    ax.set_title(f"Só {str(round(exp, 1)).replace(chr(46), chr(44))}% das conversas caem no expediente; o resto é noite e fim de semana", pad=18)
    salvar(fig, "eda4_quando_usam.png")

    # 5. dispositivo e navegador --------------------------------------------------------------------
    so = consulta(cur, """SELECT sistema, count(*) FILTER (WHERE voltou_7d), count(*) FROM silver.fato_usuario WHERE pais='Brazil' AND elegivel AND sistema <> 'Outro'
                          GROUP BY 1 ORDER BY 3 DESC""")
    nav = consulta(cur, """SELECT navegador, count(*) FILTER (WHERE voltou_7d), count(*) FROM silver.fato_usuario WHERE pais='Brazil' AND elegivel AND navegador <> 'Outro'
                           GROUP BY 1 ORDER BY 3 DESC""")
    fig, axs = plt.subplots(1, 2, figsize=(10.4, 3.8), sharex=True)
    for ax, dados, tit in ((axs[0], so, "Sistema"), (axs[1], nav, "Navegador")):
        cores = [VERM if r[0] in ("iOS", "Mac", "Safari") else ROXO for r in dados]
        pontos_ic(ax, [r[0] for r in dados], [r[1] for r in dados], [r[2] for r in dados], cores, media)
        ax.set_title(tit, fontsize=11)
    fig.suptitle("Mobile e desktop voltam igual; o ecossistema Apple volta menos (pode ser efeito da medida)", x=0.01, y=1.0, ha="left", fontsize=11.5, fontweight="bold")
    fig.subplots_adjust(top=0.82, wspace=0.55)
    salvar(fig, "eda5_dispositivo.png")

    # 6. recusa e saudação dentro de cada família de modelo -------------------------------------------
    rec = consulta(cur, """SELECT CASE WHEN modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END fam, recusa, count(*) FILTER (WHERE voltou_7d), count(*)
                           FROM silver.fato_usuario WHERE pais='Brazil' AND elegivel AND recusa IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""")
    sau = consulta(cur, """SELECT CASE WHEN u.modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END fam, t.tema = 'Saudação', count(*) FILTER (WHERE u.voltou_7d), count(*)
                           FROM silver.fato_usuario u JOIN silver.dim_tema t USING (tema_id) WHERE u.pais='Brazil' AND u.elegivel GROUP BY 1,2 ORDER BY 1,2""")
    fig, axs = plt.subplots(1, 2, figsize=(10.4, 3.6), sharex=True)
    for ax, dados, tit, rot in ((axs[0], rec, "Recusa na 1ª resposta", ("sem recusa", "com recusa")), (axs[1], sau, "Abertura com saudação", ("outro tema", "saudação"))):
        rotulos = [f"{r[0]}, {rot[1] if r[1] else rot[0]}" for r in dados]
        cores = [VERM if r[1] else ROXO for r in dados]
        pontos_ic(ax, rotulos, [r[2] for r in dados], [r[3] for r in dados], cores, media)
        ax.set_title(tit, fontsize=11)
    fig.suptitle("A saudação pesa nos dois modelos; a recusa pesa sobretudo no GPT-4", x=0.01, y=1.0, ha="left", fontsize=11.5, fontweight="bold")
    fig.subplots_adjust(top=0.82, wspace=0.75)
    salvar(fig, "eda6_efeitos_por_modelo.png")

    # 7. idioma do pedido x idioma do navegador -------------------------------------------------------
    lg = consulta(cur, """WITH p AS (
          SELECT u.elegivel, u.voltou_7d, f.idioma, lower(split_part(coalesce(b.header->>'accept-language',''), ',', 1)) al
          FROM silver.fato_usuario u JOIN silver.fato_conversa f ON f.usuario_id = u.usuario_id AND f.pais = u.pais AND f.inicio_utc = u.primeira_vez_utc
          JOIN bronze.wildchat b ON b.bronze_id = f.bronze_id WHERE u.pais='Brazil')
        SELECT CASE WHEN al LIKE 'pt%' AND idioma='Portuguese' THEN 'navegador PT, pedido em português'
                    WHEN al LIKE 'pt%' AND idioma='English' THEN 'navegador PT, pedido em inglês'
                    WHEN al LIKE 'pt%' THEN 'navegador PT, pedido em outro idioma'
                    WHEN al = '' THEN 'sem idioma no navegador' ELSE 'navegador em outro idioma' END g,
               count(*) FILTER (WHERE elegivel AND voltou_7d), count(*) FILTER (WHERE elegivel)
        FROM p GROUP BY 1 ORDER BY 3 DESC""")
    lg = [r for r in lg if r[2] >= 30]
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    pontos_ic(ax, [r[0] for r in lg], [r[1] for r in lg], [r[2] for r in lg], [VERM if "pedido em outro idioma" in r[0] else ROXO for r in lg], media)
    ax.set_title("Navegador em português e pedido em outro idioma (nem PT nem inglês): volta menos")
    salvar(fig, "eda7_idioma.png")

print("pronto: figuras em", SAIDA, "| usuários na curva de retorno:", n_curva)
