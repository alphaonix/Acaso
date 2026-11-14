"""Conferencias da SILVER, em tres grupos:
  bronze_silver  nada some da bronze sem registro (bronze = silver + excluidas)
  silver_interna a silver e coerente; o retorno, a elegibilidade e a 1a vez sao RECALCULADOS a partir das conversas
  validados      os numeros principais do Brasil continuam iguais aos que conferi a mao (Power BI e DBeaver; docs/VALIDACAO.md)
Cada linha: (grupo, o que confere, valor esperado, SQL que devolve um unico valor). Se algo diferir, a carga e desfeita."""
from comum.definicoes import GAP_SESSAO_MIN, JANELA_RETORNO_DIAS, LAVAGEM_DIAS
from comum.qualidade import Resultado, executar

# Recalculo do retorno: parte so das conversas (silver.fato_conversa), numera as sessoes de novo e compara com o que a
# silver guardou em fato_usuario. Qualquer divergencia em voltou_7d, elegivel ou primeira vez derruba a carga.
# (Limite: nao testa a derivacao do usuario_id e do inicio, que acontece antes; isso o analise/08_recalculo_independente.py cobre.)
_RECALCULO = f"""
WITH o AS (SELECT pais, usuario_id, inicio_utc, fim_utc,
             CASE WHEN lag(fim_utc) OVER w IS NULL OR inicio_utc - lag(fim_utc) OVER w > INTERVAL '{GAP_SESSAO_MIN} minutes' THEN 1 ELSE 0 END AS nova
           FROM silver.fato_conversa WINDOW w AS (PARTITION BY pais, usuario_id ORDER BY inicio_utc, fim_utc)),
s AS (SELECT *, sum(nova) OVER (PARTITION BY pais, usuario_id ORDER BY inicio_utc, fim_utc) AS sessao,
             min(inicio_utc) OVER (PARTITION BY pais, usuario_id) AS primeira FROM o),
r AS (SELECT pais, usuario_id, min(primeira) AS primeira,
             bool_or(sessao > 1 AND inicio_utc <= primeira + INTERVAL '{JANELA_RETORNO_DIAS} days') AS voltou FROM s GROUP BY 1, 2),
lim AS (SELECT pais, min(inicio_utc) AS mn, max(inicio_utc) AS mx FROM silver.fato_conversa GROUP BY 1)
SELECT count(*) FILTER (WHERE {{criterio}})
FROM r JOIN silver.fato_usuario u USING (pais, usuario_id) JOIN lim l USING (pais)"""

VERIFICACOES = [
    ("bronze_silver", "Linhas da bronze = conversas da silver + linhas excluidas", "0",
     "SELECT (SELECT count(*) FROM bronze.wildchat) - (SELECT count(*) FROM silver.fato_conversa) - (SELECT count(*) FROM auditoria.registro_excluido WHERE execucao_id = %(exec)s)"),
    ("bronze_silver", "Toda conversa da silver aponta para uma linha existente da bronze", "0",
     "SELECT count(*) FROM silver.fato_conversa f LEFT JOIN bronze.wildchat b USING (bronze_id) WHERE b.bronze_id IS NULL"),
    ("bronze_silver", "Pais nulo na bronze = Desconhecido na silver + excluidas", "0",
     "SELECT (SELECT count(*) FROM bronze.wildchat WHERE country IS NULL) - (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Desconhecido') - (SELECT count(*) FROM auditoria.registro_excluido WHERE execucao_id = %(exec)s AND pais = 'Desconhecido')"),
    ("silver_interna", "Usuarios distintos nas conversas = usuarios (Brasil)", "0",
     "SELECT (SELECT count(DISTINCT usuario_id) FROM silver.fato_conversa WHERE pais = 'Brazil') - (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil')"),
    ("silver_interna", "Soma de conversas por usuario = conversas (todos os paises)", "0",
     "SELECT (SELECT sum(convs_total) FROM silver.fato_usuario) - (SELECT count(*) FROM silver.fato_conversa)"),
    ("silver_interna", "Todo pais (exceto Desconhecido) tem codigo ISO para o nome na lingua da tela", "0",
     "SELECT count(*) FROM silver.dim_pais WHERE iso2 IS NULL AND pais <> 'Desconhecido'"),
    ("silver_interna", "Nenhum usuario_id em dois paises", "0",
     "SELECT count(*) FROM (SELECT usuario_id FROM silver.fato_usuario GROUP BY 1 HAVING count(*) > 1) x"),
    ("silver_interna", "Retorno recalculado a partir das conversas = voltou_7d da silver (usuarios com divergencia)", "0",
     _RECALCULO.format(criterio="r.voltou IS DISTINCT FROM u.voltou_7d")),
    ("silver_interna", "Elegibilidade recalculada = elegivel da silver (usuarios com divergencia)", "0",
     _RECALCULO.format(criterio=f"(r.primeira >= l.mn + INTERVAL '{LAVAGEM_DIAS} days' AND r.primeira <= l.mx - INTERVAL '{JANELA_RETORNO_DIAS} days') IS DISTINCT FROM u.elegivel")),
    ("silver_interna", "Primeira vez recalculada = primeira_vez_utc da silver (usuarios com divergencia)", "0",
     _RECALCULO.format(criterio="r.primeira IS DISTINCT FROM u.primeira_vez_utc")),
    ("silver_interna", "Voltou em 24 h implica voltou em 7 dias (usuarios que violam)", "0",
     "SELECT count(*) FROM silver.fato_usuario WHERE voltou_24h AND NOT voltou_7d"),
    ("validados", "Conversas do Brasil (silver)", "11621", "SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil'"),
    ("validados", "Usuarios do Brasil", "2530", "SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil'"),
    ("validados", "Usuarios elegiveis do Brasil", "2234", "SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel"),
    ("validados", "Retorno em 7 dias do Brasil (4 casas)", "0.2372",
     "SELECT round((count(*) FILTER (WHERE voltou_7d))::numeric / count(*), 4) FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel"),
    ("validados", "Usuarios em Sao Paulo", "848",
     "SELECT count(DISTINCT usuario_id) FROM silver.fato_conversa WHERE pais = 'Brazil' AND estado = 'São Paulo'"),
    ("validados", "Usuarios em Minas Gerais", "251",
     "SELECT count(DISTINCT usuario_id) FROM silver.fato_conversa WHERE pais = 'Brazil' AND estado = 'Minas Gerais'"),
    ("validados", "Conversas com recusa (Brasil)", "911", "SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil' AND recusa"),
    ("validados", "Usuarios com recusa na 1a conversa (Brasil)", "230", "SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil' AND recusa"),
    ("validados", "Conversas redigidas (Brasil)", "56", "SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil' AND redigida"),
    ("validados", "Usuarios do Brasil por tema (11 temas, na ordem da taxonomia)", "72,431,16,102,21,256,106,266,141,607,512",
     "SELECT string_agg(n::text, ',' ORDER BY tema_id) FROM (SELECT tema_id, count(*) AS n FROM silver.fato_usuario WHERE pais = 'Brazil' GROUP BY tema_id) x"),
]


def validar_silver(dw, execucao_id: int) -> list[Resultado]:
    return executar(dw, VERIFICACOES, execucao_id)
