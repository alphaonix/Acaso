"""Estimacao dos efeitos no retorno em 7 dias (silver -> gold.efeito_fator). Metodo e premissas: docs/bdr/BDR-004.

Para cada fator (tratamento binario) comparamos usuarios PARECIDOS: o efeito e a diferenca de retorno em pontos
percentuais, ajustada por covariaveis anteriores ao tratamento, com o estimador AIPW (duplamente robusto) e validacao
cruzada. Reportamos tambem o efeito bruto, a sobreposicao entre grupos e o E-value (sensibilidade a confusao nao medida).
Prova: associacao ajustada pelo que foi observado. NAO prova causa: ha confusao nao medida (ex.: engajamento previo).
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

PAIS = "Brazil"          # pais da analise (o desafio); estimar outros paises e extensao natural
K_DOBRAS = 5
SEMENTE = 42
MIN_GRUPO = 30           # abaixo disso o efeito nao e estimado (a tela mostra "amostra pequena demais")
CORTE = (0.025, 0.975)   # corte do escore de propensao (evita pesos extremos)
TEMA_REF = "Conhecimento/pergunta"
METODO = "AIPW (duplamente robusto), validação cruzada 5 dobras, regressão logística L2"

SQL = """SELECT u.usuario_id, u.voltou_7d::int AS y, u.modelo, u.idioma, u.turnos, u.prompt1_chars, u.resp1_chars,
                u.recusa::int AS recusa, t.tema, u.hora, u.dia_semana, to_char(u.semana, 'YYYY-MM') AS mes,
                u.navegador, u.sistema, u.estado
         FROM silver.fato_usuario u LEFT JOIN silver.dim_tema t USING (tema_id)
         WHERE u.pais = %s AND u.elegivel"""


def _carregar(dw) -> pd.DataFrame:
    with dw.cursor() as cur:
        cur.execute(SQL, (PAIS,))
        cols = [d.name for d in cur.description]
        # Ordem FIXA: a divisao em dobras (validacao cruzada) depende da ordem das linhas; sem isso o resultado muda
        # a cada carga. Ordenar por usuario_id torna o efeito reproduzivel (verificado: mesma carga, mesmo numero).
        return pd.DataFrame(cur.fetchall(), columns=cols).sort_values("usuario_id").reset_index(drop=True)


def _preparar(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["modelo_fam"] = np.where(d["modelo"].str.startswith("gpt-4"), "GPT-4", "GPT-3.5")
    d["idioma_grp"] = np.where(d["idioma"].isin(["Portuguese", "English"]), d["idioma"], "Outro")
    d["periodo"] = pd.cut(d["hora"], [-1, 5, 11, 17, 23], labels=["madrugada", "manha", "tarde", "noite"]).astype(str)
    d["fds"] = (d["dia_semana"] >= 6).astype(int).astype(str)
    d["pedido_bin"] = pd.cut(d["prompt1_chars"], [-1, 20, 100, 500, 10**9], labels=["<=20", "21-100", "101-500", ">500"]).astype(str)
    top = d["estado"].value_counts().head(5).index
    d["estado_grp"] = np.where(d["estado"].isin(top), d["estado"], "Outro/sem estado")
    d["navegador"] = d["navegador"].fillna("Outro")
    d["sistema"] = d["sistema"].fillna("Outro")
    d["tema"] = d["tema"].fillna("Outro")
    d["mediana_resp"] = d["resp1_chars"].median()
    d["mediana_pedido"] = d["prompt1_chars"].median()
    return d


def _e_value(rr: float) -> float:
    rr = rr if rr >= 1 else 1 / rr
    return rr + np.sqrt(rr * (rr - 1))


def _aipw(y: np.ndarray, t: np.ndarray, X: np.ndarray) -> dict:
    n = len(y)
    e, m1, m0 = np.zeros(n), np.zeros(n), np.zeros(n)
    for tr, te in StratifiedKFold(K_DOBRAS, shuffle=True, random_state=SEMENTE).split(X, t):
        e[te] = LogisticRegression(C=1.0, max_iter=2000).fit(X[tr], t[tr]).predict_proba(X[te])[:, 1]
        for val, alvo in ((1, m1), (0, m0)):
            idx = tr[t[tr] == val]
            if len(idx) < 10 or y[idx].min() == y[idx].max():
                alvo[te] = y[idx].mean()
            else:
                alvo[te] = LogisticRegression(C=1.0, max_iter=2000).fit(X[idx], y[idx]).predict_proba(X[te])[:, 1]
    e = np.clip(e, *CORTE)
    psi = m1 - m0 + t * (y - m1) / e - (1 - t) * (y - m0) / (1 - e)
    tau, se = psi.mean(), psi.std(ddof=1) / np.sqrt(n)
    return dict(tau=tau, lo=tau - 1.96 * se, hi=tau + 1.96 * se, p0=float(np.clip(m0.mean(), 1e-6, 1 - 1e-6)),
                sobreposicao=float(((e > 0.05) & (e < 0.95)).mean()))


def _bruto(y: np.ndarray, t: np.ndarray) -> tuple[float, float, float, float]:
    y1, y0 = y[t == 1], y[t == 0]
    diff = y1.mean() - y0.mean()
    se = np.sqrt(y1.mean() * (1 - y1.mean()) / len(y1) + y0.mean() * (1 - y0.mean()) / len(y0))
    return diff, diff - 1.96 * se, diff + 1.96 * se, y0.mean()


def _linha(d: pd.DataFrame, mask: pd.Series, t: pd.Series, covs: list[str], fator: str, contraste: str, tipo: str):
    sub, ts = d[mask], t[mask].astype(int).to_numpy()
    n1, n0 = int(ts.sum()), int(len(ts) - ts.sum())
    if n1 < MIN_GRUPO or n0 < MIN_GRUPO:
        return None
    y = sub["y"].to_numpy(dtype=float)
    X = pd.get_dummies(sub[covs].astype(str), drop_first=True).to_numpy(dtype=float)
    r, (bd, blo, bhi, _) = _aipw(y, ts, X), _bruto(y, ts)
    p0 = r["p0"]
    rr = (p0 + r["tau"]) / p0
    ev = _e_value(rr)
    lim = r["lo"] if r["tau"] >= 0 else r["hi"]            # limite do IC mais proximo de zero
    ev_ic = 1.0 if (r["lo"] <= 0 <= r["hi"]) else _e_value((p0 + lim) / p0)
    return (PAIS, fator, contraste, tipo, len(ts), n1, n0, round(float(y[ts == 0].mean()), 4),
            round(100 * bd, 2), round(100 * blo, 2), round(100 * bhi, 2),
            round(100 * r["tau"], 2), round(100 * r["lo"], 2), round(100 * r["hi"], 2),
            round(100 * r["sobreposicao"], 1), round(float(ev), 2), round(float(ev_ic), 2), METODO, ", ".join(covs))


def calcular(dw) -> list[tuple]:
    """Calcula os efeitos sem gravar. Usado pelo ETL e pelos testes de sensibilidade (analise/04)."""
    d = _preparar(_carregar(dw))
    B = ["mes", "periodo", "fds", "sistema", "navegador", "estado_grp"]          # calendario, dispositivo, regiao
    sem = lambda *x: [c for c in B if c not in x]
    todos = pd.Series(True, index=d.index)
    linhas = [
        _linha(d, todos, d["modelo_fam"] == "GPT-4", B + ["tema", "pedido_bin", "idioma_grp"],
               "Modelo", "GPT-4 em vez de GPT-3.5", "alavanca"),
        _linha(d, todos, d["recusa"] == 1, B + ["modelo_fam", "tema", "pedido_bin", "idioma_grp"],
               "Recusa na primeira resposta", "Com recusa em vez de sem", "alavanca"),
        _linha(d, todos, d["resp1_chars"] >= d["mediana_resp"], B + ["modelo_fam", "tema", "pedido_bin", "idioma_grp"],
               "Tamanho da primeira resposta", f"Longa (>= {int(d['mediana_resp'].iloc[0])} caracteres) em vez de curta", "alavanca"),
        _linha(d, todos, d["turnos"] >= 2, B + ["modelo_fam", "tema", "pedido_bin", "idioma_grp"],
               "Turnos da primeira conversa", "2 ou mais em vez de 1", "perfil"),
        _linha(d, todos, d["prompt1_chars"] >= d["mediana_pedido"], B + ["modelo_fam", "idioma_grp"],
               "Tamanho do primeiro pedido", f"Longo (>= {int(d['mediana_pedido'].iloc[0])} caracteres) em vez de curto", "perfil"),
        _linha(d, todos, d["periodo"] == "noite", sem("periodo") + ["modelo_fam", "idioma_grp"],
               "Horário", "Noite (18-23h) em vez de outros períodos", "perfil"),
        _linha(d, todos, d["fds"] == "1", sem("fds") + ["modelo_fam", "idioma_grp"],
               "Dia da semana", "Fim de semana em vez de dia útil", "perfil"),
        _linha(d, d["idioma_grp"].isin(["Portuguese", "English"]), d["idioma_grp"] == "English", B + ["modelo_fam"],
               "Idioma", "Inglês em vez de português", "perfil"),
    ]
    for tema in sorted(d["tema"].unique()):
        if tema != TEMA_REF:
            linhas.append(_linha(d, d["tema"].isin([tema, TEMA_REF]), d["tema"] == tema,
                                 B + ["idioma_grp", "modelo_fam"], "Tema do primeiro pedido",
                                 f"{tema} em vez de {TEMA_REF}", "perfil"))
    return [l for l in linhas if l is not None]


def construir_efeitos(dw) -> int:
    """Calcula e grava gold.efeito_fator (dentro da transacao `dw`). Devolve o numero de efeitos."""
    linhas = calcular(dw)
    with dw.cursor() as cur:
        cur.executemany("INSERT INTO gold.efeito_fator VALUES (" + ", ".join(["%s"] * 19) + ")", linhas)
    return len(linhas)
