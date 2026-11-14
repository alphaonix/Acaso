"""Conferencias da BRONZE: o que entrou bate com os arquivos da semente?
Cada linha: (grupo, o que confere, valor esperado, SQL que devolve um unico valor). `%(exec)s` = numero da execucao do ETL.
Se algo diferir, a carga e desfeita (rollback) e nada e publicado."""
from comum.qualidade import Resultado, executar

VERIFICACOES = [
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
]


def validar_bronze(dw, execucao_id: int) -> list[Resultado]:
    return executar(dw, VERIFICACOES, execucao_id)
