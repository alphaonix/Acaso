"""RECALCULO INDEPENDENTE da Silver: refaz, em Python (pandas), a identidade da pessoa, as visitas, o retorno e a elegibilidade a partir
da BRONZE e compara com o que a Silver gravou, pessoa por pessoa.

Por que existe: as conferencias em SQL da propria silver (silver/validar.py) recalculam as visitas a partir de silver.fato_conversa,
mas nao testam a derivacao do codigo da pessoa, do navegador e do inicio, que acontece ANTES. Este recalculo parte do dado cru,
com outro codigo e outra linguagem: se os dois chegarem ao mesmo resultado, o erro de implementacao e improvavel.

Mesmas regras de negocio de comum/definicoes.py (30 min, 7 dias, 30 dias de lavagem), implementadas aqui por conta propria."""
import hashlib

import numpy as np
import pandas as pd

from comum.definicoes import GAP_SESSAO_MIN, JANELA_RETORNO_DIAS, LAVAGEM_DIAS

SQL_BRONZE = """SELECT conversation_hash AS h, hashed_ip AS ip, "timestamp" AS fim, primeira_resposta_ts AS ini,
                       coalesce(country, 'Desconhecido') AS pais, header->>'user-agent' AS ua
                FROM bronze.wildchat WHERE %(todos)s OR coalesce(country, 'Desconhecido') = ANY(%(paises)s::text[])"""

SQL_SILVER = """SELECT usuario_id, pais, voltou_7d, voltou_24h, elegivel, primeira_vez_utc, convs_total FROM silver.fato_usuario
                WHERE %(todos)s OR pais = ANY(%(paises)s::text[])"""


def _ler(dw, sql: str, colunas: list[str], paises: list[str] | None) -> pd.DataFrame:
    with dw.cursor() as cur:
        cur.execute(sql, {"todos": paises is None, "paises": paises or []})
        return pd.DataFrame(cur.fetchall(), columns=colunas)


def recalcular(df: pd.DataFrame) -> pd.DataFrame:
    """df: colunas h, ip, fim, ini, pais, ua. Devolve uma linha por pessoa (pais, usuario_id, primeira, voltou7, voltou24, elegivel, n)."""
    df = df[df["ini"].notna() & df["ip"].notna()].copy()
    df = df.sort_values(["h", "ip", "ini", "fim"]).drop_duplicates(["h", "ip", "ini"])      # copia exata (hash + ip + inicio)
    ua = df["ua"].fillna("").str.lower()
    navegador = np.select([ua.str.contains("edg/"), ua.str.contains("opr/"), ua.str.contains("firefox"), ua.str.contains("chrome"),
                           ua.str.contains("safari")], ["Edge", "Opera", "Firefox", "Chrome", "Safari"], "Outro")
    sistema = np.select([ua.str.contains("android"), ua.str.contains("iphone") | ua.str.contains("ipad"), ua.str.contains("windows"),
                         ua.str.contains("mac os"), ua.str.contains("linux")], ["Android", "iOS", "Windows", "Mac", "Linux"], "Outro")
    df["uk"] = df["ip"] + "|" + pd.Series(navegador, index=df.index) + "/" + pd.Series(sistema, index=df.index)

    df = df.sort_values(["pais", "uk", "ini", "fim"])
    grupo = df.groupby(["pais", "uk"], sort=False)
    fim_anterior = grupo["fim"].shift(1)
    nova_visita = fim_anterior.isna() | ((df["ini"] - fim_anterior) > pd.Timedelta(minutes=GAP_SESSAO_MIN))
    df["visita"] = nova_visita.astype(int).groupby([df["pais"], df["uk"]], sort=False).cumsum()
    df["primeira"] = grupo["ini"].transform("min")
    df["ret7"] = (df["visita"] > 1) & (df["ini"] <= df["primeira"] + pd.Timedelta(days=JANELA_RETORNO_DIAS))
    df["ret24"] = (df["visita"] > 1) & (df["ini"] <= df["primeira"] + pd.Timedelta(days=1))
    pessoas = df.groupby(["pais", "uk"], sort=False).agg(primeira=("ini", "min"), voltou7=("ret7", "max"), voltou24=("ret24", "max"),
                                                       n=("ini", "size")).reset_index()
    limites = df.groupby("pais")["ini"].agg(mn="min", mx="max")
    pessoas = pessoas.join(limites, on="pais")
    pessoas["elegivel"] = ((pessoas["primeira"] >= pessoas["mn"] + pd.Timedelta(days=LAVAGEM_DIAS))
                           & (pessoas["primeira"] <= pessoas["mx"] - pd.Timedelta(days=JANELA_RETORNO_DIAS)))
    pessoas["usuario_id"] = pessoas["uk"].map(lambda s: hashlib.md5(s.encode()).hexdigest()[:12])
    return pessoas


def divergencias(dw, paises: list[str] | None = None) -> dict[str, int]:
    """Compara o recalculo com silver.fato_usuario. `paises=None` confere todos. Cada valor e uma contagem de pessoas (esperado: 0)."""
    cru = _ler(dw, SQL_BRONZE, ["h", "ip", "fim", "ini", "pais", "ua"], paises)
    silver = _ler(dw, SQL_SILVER, ["usuario_id", "pais", "voltou7_s", "voltou24_s", "elegivel_s", "primeira_s", "n_s"], paises)
    mix = recalcular(cru).merge(silver, on=["usuario_id", "pais"], how="outer", indicator=True)
    ambos = mix[mix["_merge"] == "both"]
    return {
        "pessoas_em_um_lado_so": int((mix["_merge"] != "both").sum()),
        "voltou_7d": int((ambos["voltou7"] != ambos["voltou7_s"]).sum()),
        "voltou_24h": int((ambos["voltou24"] != ambos["voltou24_s"]).sum()),
        "elegivel": int((ambos["elegivel"] != ambos["elegivel_s"]).sum()),
        "primeira_vez": int((ambos["primeira"] != ambos["primeira_s"]).sum()),
        "convs_total": int((ambos["n"] != ambos["n_s"]).sum()),
        "pessoas_comparadas": int(len(ambos)),
    }
