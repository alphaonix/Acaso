"""Silver -> Gold: agregados, catalogo e lista de paises. Tudo em SQL no Postgres (o mesmo SQL esta no catalogo).
Taxa e IC (Wilson 95%) so aparecem com amostra >= AMOSTRA_MINIMA; abaixo disso ficam NULL e a tela avisa.
"""
from .definicoes import AMOSTRA_MINIMA, CATALOGO

M = AMOSTRA_MINIMA

SQL_PAIS = """
INSERT INTO gold.pais (pais, nome_exibicao, fuso, fuso_aproximado, idioma_padrao, tem_texto, usuarios, usuarios_elegiveis, conversas,
                       primeira_data, ultima_data, iso2, turnos_medios, turnos_mediana, pct_gpt4)
SELECT d.pais, d.nome_exibicao, d.fuso, d.fuso_aproximado, d.idioma_padrao, d.tem_texto,
       u.usuarios, u.elegiveis, c.conversas, c.primeira, c.ultima, d.iso2, u.turnos_medios, u.turnos_mediana, u.pct_gpt4
FROM silver.dim_pais d
JOIN (SELECT pais, count(*) AS usuarios, count(*) FILTER (WHERE elegivel) AS elegiveis,
             avg(turnos) AS turnos_medios, percentile_cont(0.5) WITHIN GROUP (ORDER BY turnos) AS turnos_mediana,
             avg((modelo LIKE 'gpt-4%')::int) AS pct_gpt4
      FROM silver.fato_usuario GROUP BY pais) u USING (pais)
JOIN (SELECT pais, count(*) AS conversas, min(inicio_utc)::date AS primeira, max(inicio_utc)::date AS ultima
      FROM silver.fato_conversa GROUP BY pais) c USING (pais)
"""

SQL_RETORNO_SEMANA = f"""
INSERT INTO gold.agg_retorno_semana
SELECT pais, semana, count(*), count(*) FILTER (WHERE elegivel), count(*) FILTER (WHERE elegivel AND voltou_7d),
       CASE WHEN count(*) FILTER (WHERE elegivel) >= {M}
            THEN (count(*) FILTER (WHERE elegivel AND voltou_7d))::numeric / count(*) FILTER (WHERE elegivel) END,
       CASE WHEN count(*) FILTER (WHERE elegivel) >= {M}
            THEN gold.wilson_lo(count(*) FILTER (WHERE elegivel AND voltou_7d), count(*) FILTER (WHERE elegivel)) END,
       CASE WHEN count(*) FILTER (WHERE elegivel) >= {M}
            THEN gold.wilson_hi(count(*) FILTER (WHERE elegivel AND voltou_7d), count(*) FILTER (WHERE elegivel)) END
FROM silver.fato_usuario GROUP BY pais, semana
"""

# Os fatores e seus niveis (faixas legiveis para quem nao e tecnico), definidos UMA vez e usados no agregado total e no mensal.
# Cada usuario gera uma linha por fator; `t` e o tema (silver.dim_tema) e `u` o usuario (silver.fato_usuario).
_FATORES_VALUES = """
    ('modelo', CASE WHEN u.modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END),
    ('idioma', coalesce(u.idioma, '(sem idioma)')),
    ('periodo_do_dia', CASE WHEN u.hora < 6 THEN 'Madrugada (0-5h)' WHEN u.hora < 12 THEN 'Manhã (6-11h)'
                            WHEN u.hora < 18 THEN 'Tarde (12-17h)' ELSE 'Noite (18-23h)' END),
    ('dia_da_semana', CASE WHEN u.dia_semana >= 6 THEN 'Fim de semana' ELSE 'Dia útil' END),
    ('turnos_da_primeira_conversa', CASE WHEN u.turnos = 1 THEN '1 turno' WHEN u.turnos <= 3 THEN '2-3 turnos'
                                         WHEN u.turnos <= 6 THEN '4-6 turnos' ELSE '7+ turnos' END),
    ('tema', t.tema),
    ('recusa', CASE WHEN u.recusa IS NULL THEN NULL WHEN u.recusa THEN 'Com recusa' ELSE 'Sem recusa' END),
    ('tamanho_do_pedido', CASE WHEN u.prompt1_chars IS NULL THEN NULL WHEN u.prompt1_chars <= 20 THEN 'Até 20 caracteres'
                               WHEN u.prompt1_chars <= 100 THEN '21-100' WHEN u.prompt1_chars <= 500 THEN '101-500'
                               ELSE 'Mais de 500' END),
    ('tamanho_da_resposta', CASE WHEN u.resp1_chars IS NULL THEN NULL WHEN u.resp1_chars <= 300 THEN 'Até 300 caracteres'
                                 WHEN u.resp1_chars <= 1000 THEN '301-1.000' WHEN u.resp1_chars <= 2500 THEN '1.001-2.500'
                                 ELSE 'Mais de 2.500' END),
    ('sistema', coalesce(u.sistema, 'Outro')),
    ('navegador', coalesce(u.navegador, 'Outro')),
    ('dispositivo', CASE WHEN u.sistema IN ('Android', 'iOS') THEN 'Celular' ELSE 'Computador' END),
    ('idioma_x_navegador', CASE
        WHEN coalesce(u.idioma_navegador, '') = '' OR u.idioma IS NULL THEN NULL
        WHEN split_part(u.idioma_navegador, '-', 1) = CASE u.idioma WHEN 'English' THEN 'en' WHEN 'Portuguese' THEN 'pt' WHEN 'Spanish' THEN 'es'
             WHEN 'French' THEN 'fr' WHEN 'German' THEN 'de' WHEN 'Russian' THEN 'ru' WHEN 'Chinese' THEN 'zh' WHEN 'Japanese' THEN 'ja'
             WHEN 'Korean' THEN 'ko' WHEN 'Arabic' THEN 'ar' WHEN 'Italian' THEN 'it' WHEN 'Turkish' THEN 'tr' WHEN 'Dutch' THEN 'nl'
             WHEN 'Polish' THEN 'pl' WHEN 'Indonesian' THEN 'id' WHEN 'Vietnamese' THEN 'vi' WHEN 'Persian' THEN 'fa' WHEN 'Ukrainian' THEN 'uk'
             WHEN 'Thai' THEN 'th' ELSE NULL END THEN 'Pedido no idioma do navegador'
        WHEN u.idioma = 'English' THEN 'Inglês (navegador em outro idioma)'
        ELSE 'Outro idioma (nem o do navegador, nem inglês)' END)
"""

# Uso por dia (no fuso do pais): conversas e usuarios distintos ativos. Alimenta o grafico de uso diario.
SQL_USO_DIA = """
INSERT INTO gold.agg_uso_dia (pais, dia, conversas, usuarios_ativos)
SELECT f.pais, timezone(d.fuso, f.inicio_utc)::date, count(*), count(DISTINCT f.usuario_id)
FROM silver.fato_conversa f JOIN silver.dim_pais d ON d.pais = f.pais
GROUP BY 1, 2
"""

# Retorno por MES da primeira vez (fuso do pais) e fator: base da decomposicao "mudou o perfil ou a taxa?" (mix x taxa).
# Fatores com poucos niveis e sentido de perfil (modelo, turnos, periodo do dia, tema).
SQL_RETORNO_MES_FATOR = f"""
INSERT INTO gold.agg_retorno_mes_fator (pais, mes, fator, nivel, elegiveis, voltaram_7d)
SELECT u.pais, date_trunc('month', timezone(d.fuso, u.primeira_vez_utc))::date, f.fator, f.nivel,
       count(*), count(*) FILTER (WHERE u.voltou_7d)
FROM silver.fato_usuario u
JOIN silver.dim_pais d ON d.pais = u.pais
LEFT JOIN silver.dim_tema t ON t.tema_id = u.tema_id
CROSS JOIN LATERAL (VALUES {_FATORES_VALUES}) AS f(fator, nivel)
WHERE u.elegivel AND f.nivel IS NOT NULL AND f.fator IN ('modelo', 'turnos_da_primeira_conversa', 'periodo_do_dia', 'tema')
GROUP BY 1, 2, 3, 4
"""

SQL_RETORNO_FATOR = f"""
INSERT INTO gold.agg_retorno_fator
WITH base AS (
  SELECT u.pais, u.voltou_7d, f.fator, f.nivel
  FROM silver.fato_usuario u
  LEFT JOIN silver.dim_tema t ON t.tema_id = u.tema_id
  CROSS JOIN LATERAL (VALUES {_FATORES_VALUES}) AS f(fator, nivel)
  WHERE u.elegivel AND f.nivel IS NOT NULL
)
SELECT pais, fator, nivel, count(*), count(*) FILTER (WHERE voltou_7d),
       CASE WHEN count(*) >= {M} THEN (count(*) FILTER (WHERE voltou_7d))::numeric / count(*) END,
       CASE WHEN count(*) >= {M} THEN gold.wilson_lo(count(*) FILTER (WHERE voltou_7d), count(*)) END,
       CASE WHEN count(*) >= {M} THEN gold.wilson_hi(count(*) FILTER (WHERE voltou_7d), count(*)) END
FROM base GROUP BY pais, fator, nivel
"""


# Problemas de qualidade da base: quantas conversas cada um afeta (alimenta a tela "Glossario e qualidade").
SQL_PROBLEMAS = """
INSERT INTO gold.problema_qualidade (codigo, ordem, escopo, afetadas, total)
SELECT * FROM (
  SELECT 'pais_vazio', 1, 'todos', count(*) FILTER (WHERE country IS NULL), count(*) FROM bronze.wildchat
  UNION ALL SELECT 'estado_vazio', 2, 'todos', count(*) FILTER (WHERE estado IS NULL), count(*) FROM silver.fato_conversa
  UNION ALL SELECT 'ua_vazio', 3, 'todos', count(*) FILTER (WHERE header->>'user-agent' IS NULL), count(*) FROM bronze.wildchat
  UNION ALL SELECT 'hash_repetido', 4, 'todos',
         count(*) FILTER (WHERE conversation_hash IN (SELECT conversation_hash FROM silver.fato_conversa GROUP BY 1 HAVING count(*) > 1)),
         count(*) FROM silver.fato_conversa
  UNION ALL SELECT 'duplicata_exata', 5, 'todos',
         (SELECT count(*) FROM bronze.wildchat) - (SELECT count(*) FROM silver.fato_conversa), (SELECT count(*) FROM bronze.wildchat)
  UNION ALL SELECT 'fuso', 6, 'todos', count(*), count(*) FROM silver.fato_conversa
  UNION ALL SELECT 'sem_texto', 7, 'todos', count(*) FILTER (WHERE conversation IS NULL), count(*) FROM bronze.wildchat
  UNION ALL SELECT 'msg_usuario_sem_horario', 8, 'brasil', count(*) FILTER (WHERE conversation->0->>'timestamp' IS NULL), count(*)
         FROM bronze.wildchat WHERE conversation IS NOT NULL
  UNION ALL SELECT 'idioma_diferente', 9, 'brasil', count(*) FILTER (WHERE idioma IS DISTINCT FROM 'Portuguese'), count(*)
         FROM silver.fato_conversa WHERE pais = 'Brazil'
  UNION ALL SELECT 'usuarios_concentrados', 10, 'brasil',
         (SELECT sum(n) FROM (SELECT count(*) AS n FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY usuario_id ORDER BY 1 DESC LIMIT 10) x),
         (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')
  UNION ALL SELECT 'redigida', 11, 'brasil', count(*) FILTER (WHERE redigida), count(*) FROM silver.fato_conversa WHERE pais = 'Brazil'
) q
"""
# ---- analise ampliada (migracao 018): curva de retorno, estratos por modelo, recusa por versao, concentracao, uso por hora, modelo no tempo
SQL_CURVA = """
INSERT INTO gold.agg_curva_retorno (pais, dias, usuarios, voltaram)
SELECT u.pais, g.d, count(*), count(*) FILTER (WHERE u.dias_ate_voltar IS NOT NULL AND u.dias_ate_voltar <= g.d)
FROM silver.fato_usuario u
CROSS JOIN (VALUES (0.0), (0.25), (0.5), (1.0), (2.0), (3.0), (4.0), (5.0), (6.0), (7.0), (10.0), (14.0), (21.0), (30.0)) AS g(d)
WHERE u.janela_30d GROUP BY 1, 2
"""

SQL_ESTRATO = """
INSERT INTO gold.agg_estrato (pais, fator, familia, nivel, elegiveis, voltaram_7d)
SELECT u.pais, f.fator, CASE WHEN u.modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END, f.nivel, count(*), count(*) FILTER (WHERE u.voltou_7d)
FROM silver.fato_usuario u LEFT JOIN silver.dim_tema t ON t.tema_id = u.tema_id
CROSS JOIN LATERAL (VALUES
  ('recusa', CASE WHEN u.recusa IS NULL THEN NULL WHEN u.recusa THEN 'Com recusa' ELSE 'Sem recusa' END),
  ('saudacao', CASE WHEN t.tema IS NULL THEN NULL WHEN t.tema = 'Saudação' THEN 'Saudação' ELSE 'Outro tema' END)
) AS f(fator, nivel)
WHERE u.elegivel AND f.nivel IS NOT NULL GROUP BY 1, 2, 3, 4
"""

SQL_RECUSA_MODELO = """
INSERT INTO gold.agg_recusa_modelo (pais, modelo, conversas, conversas_texto, com_recusa, resp_media_chars, elegiveis, voltaram_7d)
WITH c AS (SELECT pais, modelo, count(*) AS conversas, count(*) FILTER (WHERE recusa IS NOT NULL) AS texto, count(*) FILTER (WHERE recusa) AS com_recusa,
                  round(avg(resp1_chars))::int AS resp
           FROM silver.fato_conversa GROUP BY 1, 2),
     u AS (SELECT pais, modelo, count(*) FILTER (WHERE elegivel) AS el, count(*) FILTER (WHERE elegivel AND voltou_7d) AS v
           FROM silver.fato_usuario GROUP BY 1, 2)
SELECT c.pais, c.modelo, c.conversas, c.texto, c.com_recusa, c.resp, coalesce(u.el, 0), coalesce(u.v, 0)
FROM c LEFT JOIN u ON u.pais = c.pais AND u.modelo = c.modelo
"""

SQL_CONCENTRACAO = """
INSERT INTO gold.agg_concentracao (pais, ordem, faixa, usuarios, conversas)
WITH u AS (SELECT pais, usuario_id, count(*) AS n FROM silver.fato_conversa GROUP BY 1, 2)
SELECT pais, ordem, faixa, count(*), sum(n) FROM (
  SELECT pais, n,
         CASE WHEN n = 1 THEN 1 WHEN n <= 3 THEN 2 WHEN n <= 10 THEN 3 ELSE 4 END AS ordem,
         CASE WHEN n = 1 THEN '1' WHEN n <= 3 THEN '2-3' WHEN n <= 10 THEN '4-10' ELSE '11+' END AS faixa
  FROM u) x GROUP BY 1, 2, 3
"""

SQL_CONCENTRACAO_PAIS = """
WITH u AS (SELECT pais, usuario_id, count(*) AS n FROM silver.fato_conversa GROUP BY 1, 2),
r AS (SELECT pais, n, row_number() OVER (PARTITION BY pais ORDER BY n DESC, usuario_id) AS rk FROM u),
t AS (SELECT pais, sum(n) AS total, sum(n) FILTER (WHERE rk <= 10) AS top10, max(n) AS maior,
             count(*) FILTER (WHERE n = 1) AS um, count(*) AS pessoas FROM r GROUP BY 1)
UPDATE gold.pais g SET top10_pct = t.top10::numeric / t.total, maior_pct = t.maior::numeric / t.total,
                       pessoas_1_conversa_pct = t.um::numeric / t.pessoas
FROM t WHERE t.pais = g.pais
"""

SQL_RETORNO_SEM_TOP10 = """
WITH u AS (SELECT pais, usuario_id, count(*) AS n FROM silver.fato_conversa GROUP BY 1, 2),
r AS (SELECT pais, usuario_id, row_number() OVER (PARTITION BY pais ORDER BY n DESC, usuario_id) AS rk FROM u),
e AS (SELECT f.pais, count(*) FILTER (WHERE f.elegivel AND f.voltou_7d) AS v_tot,
             count(*) FILTER (WHERE f.elegivel AND f.voltou_24h) AS v24,
             count(*) FILTER (WHERE f.elegivel AND coalesce(r.rk, 99) > 10) AS el_sem,
             count(*) FILTER (WHERE f.elegivel AND f.voltou_7d AND coalesce(r.rk, 99) > 10) AS v_sem
      FROM silver.fato_usuario f LEFT JOIN r ON r.pais = f.pais AND r.usuario_id = f.usuario_id GROUP BY 1)
UPDATE gold.pais g SET voltaram_24h = e.v24, voltaram_7d = e.v_tot, elegiveis_sem_top10 = e.el_sem, voltaram_sem_top10 = e.v_sem
FROM e WHERE e.pais = g.pais
"""

SQL_USO_HORA = """
INSERT INTO gold.agg_uso_hora (pais, dia_semana, hora, conversas)
SELECT f.pais, extract(isodow FROM timezone(d.fuso, f.inicio_utc))::smallint, extract(hour FROM timezone(d.fuso, f.inicio_utc))::smallint, count(*)
FROM silver.fato_conversa f JOIN silver.dim_pais d ON d.pais = f.pais GROUP BY 1, 2, 3
"""

SQL_MODELO_MES = """
INSERT INTO gold.agg_modelo_mes (pais, mes, conversas, conversas_gpt4)
SELECT f.pais, date_trunc('month', timezone(d.fuso, f.inicio_utc))::date, count(*), count(*) FILTER (WHERE f.modelo LIKE 'gpt-4%')
FROM silver.fato_conversa f JOIN silver.dim_pais d ON d.pais = f.pais GROUP BY 1, 2
"""
def construir(dw) -> None:
    """Dentro da transacao `dw`."""
    with dw.cursor() as cur:
        cur.execute(SQL_PAIS)
        cur.execute(SQL_RETORNO_SEMANA)
        cur.execute(SQL_RETORNO_FATOR)
        cur.execute(SQL_USO_DIA)
        cur.execute(SQL_RETORNO_MES_FATOR)
        cur.execute(SQL_PROBLEMAS)
        for sql in (SQL_CURVA, SQL_ESTRATO, SQL_RECUSA_MODELO, SQL_CONCENTRACAO, SQL_CONCENTRACAO_PAIS, SQL_RETORNO_SEM_TOP10, SQL_USO_HORA, SQL_MODELO_MES):
            cur.execute(sql)
        cur.executemany(
            """INSERT INTO gold.catalogo_indicador (indicador_id, nome, pergunta, unidade, denominador, formula,
               sql_referencia, fonte, periodo_referencia, amostra_minima)
               VALUES (%(indicador_id)s, %(nome)s, %(pergunta)s, %(unidade)s, %(denominador)s, %(formula)s,
                       %(sql_referencia)s, %(fonte)s, %(periodo_referencia)s, %(amostra_minima)s)""", CATALOGO)
