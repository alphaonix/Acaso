"""Os comandos SQL da SILVER (bronze -> silver), um por passo. Rodam no Postgres, dentro da transacao de carga.
A silver nasce da tabela bronze (nao dos arquivos).
Silver nao guarda texto de conversa: so variaveis derivadas. Regras em definicoes.py; razoes em docs/bdr/BDR-001 e BDR-003.

Passos (cada um vira uma tabela temporaria, que some no fim da transacao):
  bruto    achata a bronze: 1a mensagem (pedido) e 2a (resposta) saem do JSON `conversation`; uniao Brasil + demais paises
  conv0    remove repeticao EXATA (hash + ip + inicio) e linhas sem inicio ou sem ip
  conv     deriva por conversa: navegador/sistema, usuario_id, duracao, tamanhos, recusa e tema (so Brasil)
  usuarios sessoes (intervalo > 30 min), 1a experiencia, retorno em 7 dias e elegibilidade
"""
from comum.definicoes import (GAP_SESSAO_MIN, IDIOMA_PADRAO, JANELA_RETORNO_DIAS, LAVAGEM_DIAS, PAIS_COM_TEXTO, PAIS_ISO,
                         RECUSA_SQL, TEMA_SQL, TEMAS, UA_NORM_SQL, meta_pais)

SQL_BRUTO = """
CREATE TEMP TABLE bruto ON COMMIT DROP AS
SELECT bronze_id, conversation_hash, model, turn, language, state, hashed_ip, header->>'user-agent' AS ua, redacted,
       coalesce(country, 'Desconhecido') AS pais, "timestamp" AS end_ts,
       -- inicio = 1a resposta do assistente (msgs do usuario nao tem horario); a semente traz isso em primeira_resposta_ts para todos os paises
       primeira_resposta_ts AS start_ts,
       lower(split_part(coalesce(header->>'accept-language', ''), ',', 1)) AS al,   -- idioma do navegador (1a tag)
       conversation->0->>'content' AS prompt1,    -- NULL fora do Brasil (conversation e NULL)
       conversation->1->>'content' AS resp1
FROM bronze.wildchat
"""

# o mesmo conversation_hash com IP/inicio diferentes sao conversas DISTINTAS (BDR-001); so removemos repeticao exata
SQL_CONV0 = """
CREATE TEMP TABLE conv0 ON COMMIT DROP AS
SELECT DISTINCT ON (conversation_hash, hashed_ip, start_ts) * FROM bruto
WHERE start_ts IS NOT NULL AND hashed_ip IS NOT NULL
ORDER BY conversation_hash, hashed_ip, start_ts, end_ts, ua, model, bronze_id
"""

SQL_CONV = f"""
CREATE TEMP TABLE conv ON COMMIT DROP AS
SELECT *, hashed_ip || '|' || ua_norm AS uk, substr(md5(hashed_ip || '|' || ua_norm), 1, 12) AS usuario_id
FROM (
  SELECT c.*, {UA_NORM_SQL} AS ua_norm,
         (extract(epoch FROM end_ts) - extract(epoch FROM start_ts))::integer AS duracao_s,
         length(prompt1) AS prompt1_chars, length(resp1) AS resp1_chars,
         CASE WHEN pais = '{PAIS_COM_TEXTO}' THEN coalesce({RECUSA_SQL}, false) END AS recusa,
         CASE WHEN pais = '{PAIS_COM_TEXTO}' THEN ({TEMA_SQL})::smallint END AS tema_id
  FROM conv0 c
) x
"""

SQL_USUARIOS = f"""
CREATE TEMP TABLE usuarios ON COMMIT DROP AS
WITH o AS (
  SELECT conv.*, CASE WHEN lag(end_ts) OVER w IS NULL
                        OR start_ts - lag(end_ts) OVER w > INTERVAL '{GAP_SESSAO_MIN} minutes' THEN 1 ELSE 0 END AS nova
  FROM conv WINDOW w AS (PARTITION BY pais, uk ORDER BY start_ts, end_ts)),
s AS (
  SELECT o.*, sum(nova) OVER (PARTITION BY pais, uk ORDER BY start_ts, end_ts ROWS UNBOUNDED PRECEDING) AS sess,
         min(start_ts) OVER (PARTITION BY pais, uk) AS first_start
  FROM o),
a AS (
  SELECT pais, uk, count(*) AS convs_total, count(*) FILTER (WHERE sess = 1) AS convs_1a_sessao,
         coalesce(bool_or(sess > 1 AND start_ts <= first_start + INTERVAL '{JANELA_RETORNO_DIAS} days'), false) AS voltou_7d,
         coalesce(bool_or(sess > 1 AND start_ts <= first_start + INTERVAL '1 day'), false) AS voltou_24h,
         extract(epoch FROM (min(start_ts) FILTER (WHERE sess = 2) - min(first_start))) / 86400.0 AS dias_ate_voltar
  FROM s GROUP BY pais, uk),
p AS (SELECT DISTINCT ON (pais, uk) * FROM s ORDER BY pais, uk, start_ts, end_ts),
lim AS (SELECT pais, min(start_ts) AS mn, max(start_ts) AS mx FROM conv GROUP BY pais)
SELECT p.usuario_id, p.pais, p.start_ts AS primeira_vez_utc,
       date_trunc('week', timezone(d.fuso, p.start_ts))::date AS semana,
       extract(hour FROM timezone(d.fuso, p.start_ts))::smallint AS hora,
       extract(isodow FROM timezone(d.fuso, p.start_ts))::smallint AS dia_semana,
       p.model AS modelo, p.language AS idioma, p.turn AS turnos,
       split_part(p.ua_norm, '/', 1) AS navegador, split_part(p.ua_norm, '/', 2) AS sistema, p.state AS estado,
       p.prompt1_chars, p.resp1_chars, p.recusa, p.tema_id,
       a.convs_1a_sessao, a.convs_total, a.voltou_7d, a.voltou_24h, a.dias_ate_voltar,
       (p.start_ts >= l.mn + INTERVAL '{LAVAGEM_DIAS} days'
        AND p.start_ts <= l.mx - INTERVAL '{JANELA_RETORNO_DIAS} days') AS elegivel,
       (p.start_ts >= l.mn + INTERVAL '{LAVAGEM_DIAS} days'
        AND p.start_ts <= l.mx - INTERVAL '30 days') AS janela_30d,
       p.al AS idioma_navegador
FROM p JOIN a USING (pais, uk) JOIN lim l USING (pais) JOIN silver.dim_pais d ON d.pais = p.pais
"""

SQL_INSERE_CONVERSA = """
INSERT INTO silver.fato_conversa (bronze_id, conversation_hash, usuario_id, pais, estado, modelo, idioma, turnos, inicio_utc,
                                  fim_utc, duracao_s, prompt1_chars, resp1_chars, recusa, tema_id, redigida)
SELECT bronze_id, conversation_hash, usuario_id, pais, state, model, language, turn, start_ts, end_ts,
       duracao_s, prompt1_chars, resp1_chars, recusa, tema_id, redacted
FROM conv
"""

SQL_INSERE_USUARIO = """
INSERT INTO silver.fato_usuario (usuario_id, pais, primeira_vez_utc, semana, hora, dia_semana, modelo, idioma, navegador,
                                 sistema, estado, turnos, prompt1_chars, resp1_chars, recusa, tema_id, convs_1a_sessao,
                                 convs_total, voltou_7d, elegivel, voltou_24h, dias_ate_voltar, janela_30d, idioma_navegador)
SELECT usuario_id, pais, primeira_vez_utc, semana, hora, dia_semana, modelo, idioma, navegador,
       sistema, estado, turnos, prompt1_chars, resp1_chars, recusa, tema_id, convs_1a_sessao,
       convs_total, voltou_7d, elegivel, voltou_24h, dias_ate_voltar, janela_30d, idioma_navegador
FROM usuarios
"""
