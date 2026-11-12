"""Exporta tabelas planas do Brasil (sem texto das conversas) para CSV, para uso no Power BI.

Gera em exports/:
  conversas_brasil.csv   1 linha por conversa (deduplicada por hash+ip+inicio)
  usuarios_brasil.csv    1 linha por usuario, com a 1a experiencia e se voltou em 7 dias
Definicoes: ver docs/bdr/BDR-001-usuario-sessao-retorno.md
"""
import os
import duckdb

RAIZ = r"C:\Users\wande\Desktop\Acaso"
P = os.path.join(RAIZ, "data", "raw", "wildchat_todos.parquet")
OUT = os.path.join(RAIZ, "exports")
os.makedirs(OUT, exist_ok=True)

con = duckdb.connect()
con.execute("SET TimeZone='America/Sao_Paulo'")

con.execute(f"""
CREATE TEMP TABLE conv0 AS
SELECT DISTINCT ON (conversation_hash, hashed_ip, start_ts) *
FROM (
  SELECT conversation_hash, model, turn, language, state, hashed_ip,
         header['user-agent'] AS ua, redacted,
         timestamp AS end_ts,
         struct_extract(list_extract(conversation, 2), 'timestamp') AS start_ts,
         struct_extract(list_extract(conversation, 1), 'content') AS prompt1,
         struct_extract(list_extract(conversation, 2), 'content') AS resp1,
         list_sum(list_transform(conversation, lambda m: CASE WHEN m.role='user' THEN length(m.content) ELSE 0 END)) AS chars_usuario,
         list_sum(list_transform(conversation, lambda m: CASE WHEN m.role='assistant' THEN length(m.content) ELSE 0 END)) AS chars_assistente
  FROM read_parquet('{P}') WHERE country='Brazil'
)
""")

# Tema do 1o pedido: regras em ORDEM DE PRIORIDADE (a primeira que casar vence). Heuristica; validada por amostra manual.
# Referencia: docs/bdr/BDR-003-classificacao-de-tema.md
_T = "lower(substr(prompt1, 1, 600))"
TEMA_SQL = f"""CASE
  WHEN prompt1 IS NULL OR trim(prompt1) = '' THEN '01 Vazio'
  WHEN length(trim(prompt1)) <= 30 AND regexp_matches(lower(trim(prompt1)),
       '^(oi|hoi|ol[aá]|ola|hi|hello|hey|ei|eae|fala|salve|bom dia|boa tarde|boa noite|opa|e a[ií]|tudo bem)') THEN '02 Saudacao'
  WHEN regexp_matches({_T}, 'prompt generator|midjourney|stable diffusion|dall-e|dalle') THEN '03 Prompt de imagem'
  WHEN regexp_matches({_T}, 'a partir de agora|atue como|aja como|aja de|act as|you will act|quero que voc[êe] (atue|aja)|interprete|roleplay|role-play|pretend|jailbreak|ignore (all|todas)|voc[êe] [ée] um|you are a|from now on|finja') THEN '04 Persona/roleplay'
  WHEN regexp_matches({_T}, 'sexo|sex|sexual|nsfw|er[óo]tic|porn|nua |nude|seduz|orgasm|vagina|penis') THEN '05 Adulto/sensivel'
  WHEN regexp_matches({_T}, 'python|javascript|html|css|sql|c#|c[+][+]| api |c[óo]digo|code|programa|script|fun[çc][ãa]o|function|erro|error|bug|excel|planilha|f[óo]rmula|android|windows|computador|notebook|instal|linux|servidor|banco de dados|struct |vari[áa]vel|println|fabric|java|github') THEN '06 Tecnologia/codigo'
  WHEN regexp_matches({_T}, 'quest[ãa]o|marque|alternativa|considere o|exerc[íi]cio|prova |c[áa]lculo|equa[çc][ãa]o|bibliogr|metodol|tcc|artigo|resenha|fichamento|escola|universidade|aula') THEN '07 Tarefa escolar/academica'
  WHEN regexp_matches({_T}, 'reescreva|parafraseie|corrija|resuma|resumo|traduza|traduzir|tradu[çc][ãa]o|translate|rewrite|paraphrase|summar|reda[çc][ãa]o|carta|e-mail|email|legenda|copywriter|texto|melhore|revise|descri[çc][ãa]o|postagem|slogan|youtube|v[íi]deo|mensagem|nome para|um nome|elabore|redija|[ぁ-ヿ一-鿿]') THEN '08 Escrita/edicao/traducao'
  WHEN regexp_matches({_T}, 'hist[óo]ria|est[óo]ria|conto|cap[ií]tulo|chapter|roteiro|poema|poesia|m[úu]sica|letra|song|personagem|fanfic|cena|aventura|story|novel|romance|imagine|fict|quest de|rpg|miss[ãa]o') THEN '09 Ficcao/criacao'
  WHEN regexp_matches({_T}, 'o que|em que|como |qual |quais |quem |quando |onde |quanto|por que|porque|descreva|diferen[çc]a|what |how |who |why |explain|define|defina|explique|significado|liste|lista|me diga|me d[êe]|fale|cite|conhece|existe|is there|do you|can you|i want you|etimologia|cita[çc][ãa]o') THEN '10 Conhecimento/pergunta'
  ELSE '11 Outro' END"""

con.execute(f"""
CREATE TEMP TABLE conv AS
SELECT *,
  {TEMA_SQL} AS tema,
  (CASE WHEN ua ILIKE '%Edg/%' THEN 'Edge' WHEN ua ILIKE '%OPR/%' THEN 'Opera'
        WHEN ua ILIKE '%Firefox%' THEN 'Firefox' WHEN ua ILIKE '%Chrome%' THEN 'Chrome'
        WHEN ua ILIKE '%Safari%' THEN 'Safari' ELSE 'Outro' END)
  || '/' ||
  (CASE WHEN ua ILIKE '%Android%' THEN 'Android' WHEN ua ILIKE '%iPhone%' OR ua ILIKE '%iPad%' THEN 'iOS'
        WHEN ua ILIKE '%Windows%' THEN 'Windows' WHEN ua ILIKE '%Mac OS%' THEN 'Mac'
        WHEN ua ILIKE '%Linux%' THEN 'Linux' ELSE 'Outro' END) AS ua_norm,
  timezone('America/Sao_Paulo', start_ts) AS inicio_local,
  timezone('America/Sao_Paulo', end_ts) AS fim_local,
  epoch(end_ts) - epoch(start_ts) AS duracao_s,
  length(prompt1) AS prompt1_chars,
  length(resp1) AS resp1_chars,
  -- heuristica de recusa/desculpa na abertura da 1a resposta (PT e EN); validada por amostra manual
  regexp_matches(lower(substr(resp1, 1, 300)),
    'desculp|sinto muito|lamento|n[aã]o posso|n[aã]o sou capaz|n[aã]o tenho como|modelo de linguagem|como (um|uma) (ia|intelig)|i''m sorry|i am sorry|i apologize|i cannot|i can''t|i''m unable|as an ai|as a language model') AS recusa
FROM conv0
""")

con.execute(f"""COPY (
  SELECT conversation_hash, substr(md5(hashed_ip || '|' || ua_norm), 1, 12) AS usuario_id,
         md5(hashed_ip) AS ip_id, ua_norm, model, turn, language, state, redacted,
         inicio_local, fim_local, duracao_s, chars_usuario, chars_assistente,
         prompt1_chars, resp1_chars, recusa::int AS recusa, tema
  FROM conv ORDER BY inicio_local
) TO '{OUT}\\conversas_brasil.csv' (HEADER, DELIMITER ',')""")

con.execute(f"""
CREATE TEMP TABLE usuarios AS
WITH c AS (SELECT *, hashed_ip || '|' || ua_norm AS uk FROM conv),
o AS (
  SELECT *, CASE WHEN lag(end_ts) OVER w IS NULL
                   OR start_ts - lag(end_ts) OVER w > INTERVAL '30 minutes' THEN 1 ELSE 0 END AS nova
  FROM c WINDOW w AS (PARTITION BY uk ORDER BY start_ts)),
s AS (SELECT *, sum(nova) OVER (PARTITION BY uk ORDER BY start_ts ROWS UNBOUNDED PRECEDING) AS sess FROM o),
p AS (SELECT * FROM s QUALIFY row_number() OVER (PARTITION BY uk ORDER BY start_ts) = 1),
lim AS (SELECT min(start_ts) AS mn, max(start_ts) AS mx FROM conv)
SELECT substr(md5(p.uk), 1, 12) AS usuario_id,
       p.inicio_local AS primeira_vez,
       date_trunc('week', p.inicio_local)::date AS semana,
       hour(p.inicio_local) AS hora,
       dayname(p.inicio_local) AS dia_semana,
       p.model AS modelo, p.turn AS turnos, p.language AS idioma, p.ua_norm,
       p.chars_usuario, p.chars_assistente,
       p.prompt1_chars, p.resp1_chars, p.recusa::int AS recusa, p.tema,
       substr(p.prompt1, 1, 250) AS prompt_ini, substr(p.resp1, 1, 250) AS resp_ini,
       (SELECT count(*) FROM s WHERE s.uk = p.uk AND s.sess = 1) AS convs_1a_sessao,
       (SELECT count(*) FROM s WHERE s.uk = p.uk) AS convs_total,
       ((SELECT count(*) FROM s WHERE s.uk = p.uk AND s.sess > 1
           AND s.start_ts <= p.start_ts + INTERVAL '7 days') > 0)::int AS voltou_7d,
       (p.start_ts >= lim.mn + INTERVAL '30 days' AND p.start_ts <= lim.mx - INTERVAL '7 days')::int AS elegivel
FROM p, lim
""")
con.execute(f"COPY (SELECT * EXCLUDE (prompt_ini, resp_ini) FROM usuarios) TO '{OUT}\\usuarios_brasil.csv' (HEADER, DELIMITER ',')")

# Amostra para validar a heuristica de recusa A MAO (contem texto: uso local, nao compartilhar).
con.execute("SELECT setseed(0.42)")
con.execute(f"""COPY (
  (SELECT usuario_id, recusa, prompt_ini, resp_ini FROM usuarios WHERE recusa = 1 ORDER BY random() LIMIT 30)
  UNION ALL
  (SELECT usuario_id, recusa, prompt_ini, resp_ini FROM usuarios WHERE recusa = 0 ORDER BY random() LIMIT 30)
) TO '{OUT}\\amostra_validacao_recusa.csv' (HEADER, DELIMITER ',')""")
# Amostra estratificada para validar o TEMA a mao (ate 8 por tema). Uso local: contem texto.
con.execute(f"""COPY (
  SELECT usuario_id, tema, prompt_ini FROM (
    SELECT *, row_number() OVER (PARTITION BY tema ORDER BY rnd) AS rn
    FROM (SELECT *, random() AS rnd FROM usuarios)
  ) WHERE rn <= 8 ORDER BY tema
) TO '{OUT}\\amostra_validacao_tema.csv' (HEADER, DELIMITER ',')""")
print(con.sql("""SELECT tema, count(*) usuarios, round(100.0*count(*)/sum(count(*)) OVER (),1) pct,
    sum(elegivel) elegiveis, round(avg(voltou_7d) FILTER (WHERE elegivel=1),3) retorno_bruto
    FROM usuarios GROUP BY 1 ORDER BY 1""").df().to_string(index=False))
print(con.sql("SELECT round(avg(recusa),4) pct_recusa_usuarios, round(avg(voltou_7d) FILTER (WHERE recusa=1 AND elegivel=1),3) ret_recusa, round(avg(voltou_7d) FILTER (WHERE recusa=0 AND elegivel=1),3) ret_sem_recusa FROM usuarios").df().to_string(index=False))

print(con.sql("SELECT count(*) conversas FROM conv").df().to_string(index=False))
print(con.sql("""SELECT count(*) usuarios, sum(elegivel) elegiveis,
    round(avg(voltou_7d) FILTER (WHERE elegivel=1),4) retorno_7d FROM usuarios""").df().to_string(index=False))
for f in os.listdir(OUT):
    print(f, round(os.path.getsize(os.path.join(OUT, f)) / 1e6, 2), "MB")
