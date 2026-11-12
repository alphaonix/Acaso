"""Discovery 1: esquema, volume, periodo e nulos (Brasil)."""
import duckdb

P = r"C:\Users\wande\Desktop\Acaso\data\raw\wildchat_todos.parquet"
con = duckdb.connect()
con.execute(f"CREATE VIEW raw AS SELECT * FROM read_parquet('{P}')")

print("== ESQUEMA ==")
print(con.sql("DESCRIBE raw").df()[["column_name", "column_type"]].to_string(index=False))

print("\n== PAISES (top 10) ==")
print(con.sql("SELECT country, count(*) n FROM raw GROUP BY 1 ORDER BY 2 DESC LIMIT 10").df().to_string(index=False))

print("\n== BRASIL: volume, periodo, nulos ==")
print(con.sql("""
SELECT count(*) conversas,
       count(DISTINCT conversation_hash) hashes_distintos,
       count(DISTINCT hashed_ip) ips,
       min(timestamp) ts_min, max(timestamp) ts_max,
       sum((hashed_ip IS NULL)::int) ip_nulo,
       sum((header IS NULL)::int) header_nulo,
       sum((header['user-agent'] IS NULL)::int) ua_nulo,
       sum((state IS NULL)::int) state_nulo,
       sum(toxic::int) toxicas, sum(redacted::int) redigidas
FROM raw WHERE country='Brazil'
""").df().T.to_string(header=False))

print("\n== BRASIL: modelo, idioma, turnos ==")
print(con.sql("SELECT model, count(*) n FROM raw WHERE country='Brazil' GROUP BY 1 ORDER BY 2 DESC").df().to_string(index=False))
print(con.sql("SELECT language, count(*) n FROM raw WHERE country='Brazil' GROUP BY 1 ORDER BY 2 DESC LIMIT 8").df().to_string(index=False))
print(con.sql("""SELECT quantile_cont(turn,[0.5,0.9,0.99]) q, max(turn) mx, sum((turn=1)::int)/count(*) pct_1turno
FROM raw WHERE country='Brazil'""").df().to_string(index=False))

print("\n== Brasil por mes ==")
print(con.sql("""SELECT strftime(date_trunc('month', timestamp),'%Y-%m') mes, count(*) n
FROM raw WHERE country='Brazil' GROUP BY 1 ORDER BY 1""").df().to_string(index=False))
