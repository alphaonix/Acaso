"""Portao de qualidade, organizado pela TRANSICAO entre camadas que cada conferencia protege (ADR-004/005).
Compara a carga com leis de conservacao (ex.: bronze = silver + excluidas) e com numeros VALIDADOS por conferencia independente
(Power BI + DBeaver; docs/VALIDACAO.md). Se a definicao de um indicador mudar sem ninguem perceber, falha aqui.
Rodam dentro da transacao de carga: se algo falhar no modo estrito, nada e publicado (rollback).

Transicoes (a tela as mostra nesta ordem): bronze_arquivos, bronze_silver, silver_interna, silver_gold, efeitos, validados.
"""
from dataclasses import dataclass

from .definicoes import GAP_SESSAO_MIN, JANELA_RETORNO_DIAS, LAVAGEM_DIAS


@dataclass
class Resultado:
    transicao: str
    verificacao: str
    esperado: str
    obtido: str
    passou: bool

# Recalculo INDEPENDENTE do retorno: parte so das conversas (silver.fato_conversa), numera as sessoes de novo e compara com o que a
# silver guardou em fato_usuario. Qualquer divergencia em voltou_7d, elegivel ou primeira vez derruba a carga.
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

# (transicao, descricao, valor esperado, SQL que devolve um unico valor)
VERIFICACOES = [
    # --- bronze: o que entrou bate com os arquivos de origem ---
    ("bronze_arquivos", "Conversas na bronze = base completa do WildChat-1M", "837989",
     "SELECT sum(linhas) FROM ops.bronze_lote WHERE execucao_id = %(exec)s"),
    ("bronze_arquivos", "Linhas na tabela bronze.wildchat = linhas dos arquivos de origem", "0",
     "SELECT (SELECT count(*) FROM bronze.wildchat) - (SELECT sum(linhas) FROM ops.bronze_lote WHERE execucao_id = %(exec)s)"),
    ("bronze_arquivos", "Bronze: linhas do Brasil = linhas do arquivo wildchat_brasil", "11621",
     "SELECT count(*) FROM bronze.wildchat WHERE country = 'Brazil' AND arquivo_origem = 'wildchat_brasil.parquet'"),
    ("bronze_arquivos", "Bronze: nenhuma linha do Brasil veio do arquivo dos outros paises", "0",
     "SELECT count(*) FROM bronze.wildchat WHERE country = 'Brazil' AND arquivo_origem <> 'wildchat_brasil.parquet'"),
    ("bronze_arquivos", "Bronze: mensagens no JSON = 2 x turnos em todas as conversas com texto", "0",
     "SELECT count(*) FROM bronze.wildchat WHERE conversation IS NOT NULL AND jsonb_array_length(conversation) <> turn * 2"),

    # --- bronze -> silver: nada some sem registro ---
    ("bronze_silver", "Linhas da bronze = conversas da silver + linhas excluidas", "0",
     "SELECT (SELECT count(*) FROM bronze.wildchat) - (SELECT count(*) FROM silver.fato_conversa) - (SELECT count(*) FROM auditoria.registro_excluido WHERE execucao_id = %(exec)s)"),
    ("bronze_silver", "Toda conversa da silver aponta para uma linha existente da bronze", "0",
     "SELECT count(*) FROM silver.fato_conversa f LEFT JOIN bronze.wildchat b USING (bronze_id) WHERE b.bronze_id IS NULL"),
    ("bronze_silver", "Pais nulo na bronze = Desconhecido na silver + excluidas", "0",
     "SELECT (SELECT count(*) FROM bronze.wildchat WHERE country IS NULL) - (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Desconhecido') - (SELECT count(*) FROM auditoria.registro_excluido WHERE execucao_id = %(exec)s AND pais = 'Desconhecido')"),

    # --- silver: de conversa para usuario ---
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

    # --- silver -> gold: a tela mostra o que a silver tem ---
    ("silver_gold", "Gold = silver: elegiveis por semana somam os elegiveis (Brasil)", "0",
     "SELECT (SELECT sum(elegiveis) FROM gold.agg_retorno_semana WHERE pais = 'Brazil') - (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel)"),
    ("silver_gold", "Usuarios por pais: gold.pais = silver.fato_usuario", "0",
     "SELECT count(*) FROM (SELECT pais, count(*) AS n FROM silver.fato_usuario GROUP BY pais) s FULL JOIN gold.pais g USING (pais) WHERE s.n IS DISTINCT FROM g.usuarios"),
    ("silver_gold", "Conversas por pais: gold.pais = silver.fato_conversa", "0",
     "SELECT count(*) FROM (SELECT pais, count(*) AS n FROM silver.fato_conversa GROUP BY pais) s FULL JOIN gold.pais g USING (pais) WHERE s.n IS DISTINCT FROM g.conversas"),
    ("silver_gold", "Novos por semana (gold) somam os usuarios da silver, todos os paises", "0",
     "SELECT (SELECT sum(novos) FROM gold.agg_retorno_semana) - (SELECT count(*) FROM silver.fato_usuario)"),
    ("silver_gold", "Fator modelo: elegiveis somam os elegiveis da silver, todos os paises", "0",
     "SELECT (SELECT sum(elegiveis) FROM gold.agg_retorno_fator WHERE fator = 'modelo') - (SELECT count(*) FROM silver.fato_usuario WHERE elegivel)"),

    ("silver_gold", "Uso diario (gold): conversas por dia somam as conversas da silver, todos os paises", "0",
     "SELECT (SELECT sum(conversas) FROM gold.agg_uso_dia) - (SELECT count(*) FROM silver.fato_conversa)"),
    ("silver_gold", "Retorno mensal por fator (modelo): elegiveis somam os elegiveis da silver, todos os paises", "0",
     "SELECT (SELECT sum(elegiveis) FROM gold.agg_retorno_mes_fator WHERE fator = 'modelo') - (SELECT count(*) FROM silver.fato_usuario WHERE elegivel)"),

    ("silver_gold", "Retorno por semana (gold): elegiveis somam os elegiveis da silver, todos os paises", "0",
     "SELECT (SELECT sum(elegiveis) FROM gold.agg_retorno_semana) - (SELECT count(*) FROM silver.fato_usuario WHERE elegivel)"),

    # --- efeitos estimados (gold.efeito_fator) ---
    ("efeitos", "Efeitos estimados (Brasil): ha pelo menos um", "True", "SELECT count(*) > 0 FROM gold.efeito_fator WHERE pais = 'Brazil'"),
    ("efeitos", "Efeitos: IC contem a estimativa em todas as linhas", "0",
     "SELECT count(*) FROM gold.efeito_fator WHERE NOT (ic_lo <= efeito_pp AND efeito_pp <= ic_hi)"),
    ("efeitos", "Efeitos: nenhum grupo com menos de 30 usuarios", "0",
     "SELECT count(*) FROM gold.efeito_fator WHERE n_tratados < 30 OR n_controle < 30"),

    # --- numeros validados por conferencia independente (Power BI e DBeaver) ---
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


def verificar(dw, execucao_id: int) -> list[Resultado]:
    resultados = []
    with dw.cursor() as cur:
        for transicao, descricao, esperado, sql in VERIFICACOES:
            cur.execute(sql, {"exec": execucao_id})
            obtido = str(cur.fetchone()[0])
            resultados.append(Resultado(transicao, descricao, esperado, obtido, obtido == esperado))
    return resultados


def gravar(ops, execucao_id: int, resultados: list[Resultado]) -> None:
    with ops.cursor() as cur:
        cur.executemany(
            "INSERT INTO ops.qa_resultado (execucao_id, transicao, verificacao, esperado, obtido, passou) VALUES (%s, %s, %s, %s, %s, %s)",
            [(execucao_id, r.transicao, r.verificacao, r.esperado, r.obtido, r.passou) for r in resultados])
