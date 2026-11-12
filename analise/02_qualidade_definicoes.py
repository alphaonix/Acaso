"""Discovery 2: qualidade (duplicatas, timestamps, IP/UA) e sensibilidade das definicoes de usuario/retorno."""
import math
import duckdb

P = r"C:\Users\wande\Desktop\Acaso\data\raw\wildchat_todos.parquet"
con = duckdb.connect()
con.execute("SET TimeZone='America/Sao_Paulo'")
con.execute(f"""
CREATE VIEW br AS
SELECT conversation_hash, model, turn, language, hashed_ip,
       header['user-agent'] AS ua, timestamp AS end_ts,
       struct_extract(list_extract(conversation, 2), 'timestamp') AS start_ts, len(conversation) AS nmsgs
FROM read_parquet('{P}') WHERE country='Brazil'
""")

print("== QUALIDADE ==")
print(con.sql("""
SELECT count(*) n,
  sum((start_ts IS NULL)::int) sem_start,
  sum((start_ts > end_ts)::int) start_depois_do_fim,
  sum((nmsgs <> turn*2)::int) nmsgs_dif_2xturn,
  sum((turn=0)::int) turn0,
  median(epoch(end_ts)-epoch(start_ts)) dur_mediana_s,
  quantile_cont(epoch(end_ts)-epoch(start_ts),0.99) dur_p99_s
FROM br""").df().T.to_string(header=False))

print("\n== DUPLICATAS de conversation_hash ==")
print(con.sql("""
WITH d AS (SELECT conversation_hash, count(*) k,
   count(DISTINCT hashed_ip) ips, count(DISTINCT start_ts) starts
   FROM br GROUP BY 1 HAVING count(*)>1)
SELECT count(*) hashes_repetidos, sum(k) linhas, sum((ips>1)::int) com_ips_diferentes,
       sum((starts>1)::int) com_starts_diferentes FROM d""").df().to_string(index=False))

print("\n== IP / USER-AGENT ==")
print(con.sql("""
WITH x AS (SELECT hashed_ip, count(*) convs, count(DISTINCT ua) uas FROM br GROUP BY 1)
SELECT count(*) ips,
  median(convs) conv_mediana, max(convs) conv_max,
  sum((convs=1)::int)/count(*) pct_ips_1conv,
  sum((uas>1)::int)/count(*) pct_ips_multi_ua, max(uas) max_ua_por_ip,
  (SELECT sum(convs) FROM (SELECT convs FROM x ORDER BY convs DESC LIMIT 10))/(SELECT sum(convs) FROM x) top10_ips_share
FROM x""").df().T.to_string(header=False))

# ---------- sensibilidade das definicoes ----------
BASE = """
CREATE OR REPLACE TEMP TABLE conv AS
SELECT DISTINCT ON (conversation_hash, hashed_ip, start_ts)
       {key} AS uk, start_ts, end_ts
FROM br WHERE start_ts IS NOT NULL
"""

def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h

def retorno(key, gap_min, washout_d):
    con.execute(BASE.format(key=key))
    q = f"""
    WITH o AS (
      SELECT uk, start_ts, end_ts,
        CASE WHEN lag(end_ts) OVER w IS NULL
               OR start_ts - lag(end_ts) OVER w > INTERVAL '{gap_min} minutes' THEN 1 ELSE 0 END nova
      FROM conv WINDOW w AS (PARTITION BY uk ORDER BY start_ts)),
    s AS (SELECT *, sum(nova) OVER (PARTITION BY uk ORDER BY start_ts) sess FROM o),
    f AS (SELECT uk, min(start_ts) first_start FROM s GROUP BY 1),
    lim AS (SELECT min(start_ts) mn, max(start_ts) mx FROM conv)
    SELECT count(*) n,
           sum((EXISTS (SELECT 1 FROM s WHERE s.uk=f.uk AND s.sess>1
               AND s.start_ts <= f.first_start + INTERVAL '7 days'))::int) k
    FROM f, lim
    WHERE f.first_start >= lim.mn + INTERVAL '{washout_d} days'
      AND f.first_start <= lim.mx - INTERVAL '7 days'
    """
    n, k = con.execute(q).fetchone()
    lo, hi = wilson(k, n)
    return n, k, k / n if n else float("nan"), lo, hi

print("\n== RETORNO 7d: sensibilidade (n elegiveis, voltaram, taxa, IC95 Wilson) ==")
print(f"{'usuario':<10}{'gap_min':>8}{'washout_d':>10}{'n':>7}{'voltaram':>9}{'taxa':>8}{'IC95':>18}")
for key, nome in [("hashed_ip", "IP"), ("hashed_ip||'|'||ua", "IP+UA")]:
    for gap in (30, 60, 240):
        for w in (0, 30):
            n, k, r, lo, hi = retorno(key, gap, w)
            print(f"{nome:<10}{gap:>8}{w:>10}{n:>7}{k:>9}{r:>8.1%}  [{lo:.1%}, {hi:.1%}]")
