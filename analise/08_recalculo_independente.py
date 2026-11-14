"""Recalculo INDEPENDENTE (Python/pandas) a partir dos arquivos da semente, sem usar nenhum SQL do pipeline,
e comparacao com o que ficou na silver. Mesmas regras de negocio (30 min, 7 dias, 30 dias de lavagem), codigo diferente.

Rode com o compose ativo (a silver ja carregada), a partir da raiz do projeto (PowerShell):
  docker compose run --rm --no-deps -v "${PWD}\analise\08_recalculo_independente.py:/tmp/r.py:ro" etl python /tmp/r.py
Esperado: "pessoas so no Python: 0 | so na silver: 0" e zero divergencias em voltou_7d, voltou_24h, elegivel, primeira_vez e convs_total.
Leva cerca de 10 segundos e nao grava nada no banco."""
import os, hashlib, re, time
import duckdb, pandas as pd, numpy as np, psycopg

t0 = time.time()
con = duckdb.connect()
base = "/data/seed/"
q = """SELECT conversation_hash AS h, hashed_ip AS ip, "timestamp" AS fim, primeira_resposta_ts AS ini, country,
              header."user-agent" AS ua, model FROM read_parquet('{f}')"""
df = pd.concat([con.execute(q.format(f=base + n)).df() for n in ("wildchat_brasil.parquet", "wildchat_outros_paises.parquet")], ignore_index=True)
n_bruto = len(df)
df["pais"] = df["country"].fillna("Desconhecido")
df = df[df["ini"].notna() & df["ip"].notna()]
df = df.sort_values(["h", "ip", "ini", "fim"]).drop_duplicates(["h", "ip", "ini"])
n_limpo = len(df)

ua = df["ua"].fillna("").str.lower()
nav = np.select([ua.str.contains("edg/"), ua.str.contains("opr/"), ua.str.contains("firefox"), ua.str.contains("chrome"), ua.str.contains("safari")],
                ["Edge", "Opera", "Firefox", "Chrome", "Safari"], "Outro")
so = np.select([ua.str.contains("android"), ua.str.contains("iphone") | ua.str.contains("ipad"), ua.str.contains("windows"),
                ua.str.contains("mac os"), ua.str.contains("linux")], ["Android", "iOS", "Windows", "Mac", "Linux"], "Outro")
df["uk"] = df["ip"] + "|" + pd.Series(nav, index=df.index) + "/" + pd.Series(so, index=df.index)

df = df.sort_values(["pais", "uk", "ini", "fim"])
g = df.groupby(["pais", "uk"], sort=False)
prev_fim = g["fim"].shift(1)
nova = prev_fim.isna() | ((df["ini"] - prev_fim) > pd.Timedelta(minutes=30))
df["sess"] = nova.astype(int).groupby([df["pais"], df["uk"]], sort=False).cumsum()
df["primeira"] = g["ini"].transform("min")
df["ret7"] = (df["sess"] > 1) & (df["ini"] <= df["primeira"] + pd.Timedelta(days=7))
df["ret24"] = (df["sess"] > 1) & (df["ini"] <= df["primeira"] + pd.Timedelta(days=1))
u = df.groupby(["pais", "uk"], sort=False).agg(primeira=("ini", "min"), voltou7=("ret7", "max"), voltou24=("ret24", "max"), n=("ini", "size")).reset_index()
lim = df.groupby("pais")["ini"].agg(mn="min", mx="max")
u = u.join(lim, on="pais")
u["elegivel"] = (u["primeira"] >= u["mn"] + pd.Timedelta(days=30)) & (u["primeira"] <= u["mx"] - pd.Timedelta(days=7))
u["usuario_id"] = u["uk"].map(lambda s: hashlib.md5(s.encode()).hexdigest()[:12])

print(f"[python] bruto={n_bruto} limpo={n_limpo} excluidas={n_bruto - n_limpo} pessoas={len(u)} elegiveis={int(u.elegivel.sum())} "
      f"voltaram_7d_elegiveis={int((u.elegivel & u.voltou7).sum())} ({time.time() - t0:.0f}s)")
br = u[u.pais == "Brazil"]
print(f"[python] Brasil: pessoas={len(br)} elegiveis={int(br.elegivel.sum())} voltaram={int((br.elegivel & br.voltou7).sum())} "
      f"taxa={100 * (br.elegivel & br.voltou7).sum() / br.elegivel.sum():.2f}% voltou24_elegiveis={int((br.elegivel & br.voltou24).sum())}")

c = psycopg.connect(os.environ["DATABASE_URL"])
s = pd.DataFrame(c.execute("""SELECT usuario_id, pais, voltou_7d, voltou_24h, elegivel, primeira_vez_utc, convs_total FROM silver.fato_usuario""").fetchall(),
                 columns=["usuario_id", "pais", "voltou7_s", "voltou24_s", "elegivel_s", "primeira_s", "n_s"])
m = u.merge(s, on=["usuario_id", "pais"], how="outer", indicator=True)
print("[comparacao] pessoas so no Python:", int((m["_merge"] == "left_only").sum()), "| so na silver:", int((m["_merge"] == "right_only").sum()))
both = m[m["_merge"] == "both"]
print("[comparacao] divergencias em voltou_7d:", int((both.voltou7 != both.voltou7_s).sum()),
      "| voltou_24h:", int((both.voltou24 != both.voltou24_s).sum()),
      "| elegivel:", int((both.elegivel != both.elegivel_s).sum()),
      "| primeira_vez:", int((both.primeira != both.primeira_s).sum()),
      "| convs_total:", int((both.n != both.n_s).sum()))
print("[comparacao] pessoas comparadas:", len(both))

# semana de 13/11/2023 no Brasil (fuso de Sao Paulo), como na tela
b = br.copy()
loc = b["primeira"].dt.tz_convert("America/Sao_Paulo")
b["semana"] = (loc - pd.to_timedelta(loc.dt.weekday, unit="D")).dt.normalize().dt.date.astype(str)
w = b[b.semana == "2023-11-13"]
print(f"[python] semana 2023-11-13 Brasil: novos={len(w)} elegiveis={int(w.elegivel.sum())} voltaram={int((w.elegivel & w.voltou7).sum())}")