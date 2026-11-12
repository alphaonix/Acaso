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
                                 ELSE 'Mais de 2.500' END)
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
def construir(dw) -> None:
    """Dentro da transacao `dw`."""
    with dw.cursor() as cur:
        cur.execute(SQL_PAIS)
        cur.execute(SQL_RETORNO_SEMANA)
        cur.execute(SQL_RETORNO_FATOR)
        cur.execute(SQL_USO_DIA)
        cur.execute(SQL_RETORNO_MES_FATOR)
        cur.execute(SQL_PROBLEMAS)
        cur.executemany(
            """INSERT INTO gold.catalogo_indicador (indicador_id, nome, pergunta, unidade, denominador, formula,
               sql_referencia, fonte, periodo_referencia, amostra_minima)
               VALUES (%(indicador_id)s, %(nome)s, %(pergunta)s, %(unidade)s, %(denominador)s, %(formula)s,
                       %(sql_referencia)s, %(fonte)s, %(periodo_referencia)s, %(amostra_minima)s)""", CATALOGO)
