# Camada BRONZE: o dado como veio

**Em uma frase:** copia os arquivos da semente (Parquet) para uma tabela do Postgres, `bronze.wildchat`, **sem limpar nem calcular nada**.

| | |
|---|---|
| **Entra** | `data/seed/wildchat_brasil.parquet` (11.621 linhas, com texto) e `data/seed/wildchat_outros_paises.parquet` (826.368, sem texto) |
| **Sai** | `bronze.wildchat` (837.989 linhas) e o registro dos arquivos em `ops.bronze_lote` |
| **Quem enxerga** | só o ETL (o usuário da API não tem privilégio aqui, porque o Brasil tem o texto das conversas) |

## Arquivos, na ordem em que rodam
| Arquivo | O que faz |
|---|---|
| [`registrar_lotes.py`](registrar_lotes.py) | para cada arquivo: calcula o sha256 (impressão digital), conta as linhas e grava em `ops.bronze_lote` |
| [`limpar.py`](limpar.py) | esvazia `bronze.wildchat` (dentro da transação: se a carga falhar, os dados antigos voltam) |
| [`carregar.py`](carregar.py) | o DuckDB lê o Parquet, as estruturas aninhadas viram JSON, vai para um CSV temporário e entra no Postgres com `COPY` |
| [`validar.py`](validar.py) | 5 conferências: a bronze bate com os arquivos |
| [`__init__.py`](__init__.py) | `construir_bronze()` junta os três primeiros passos; `validar_bronze()` roda as conferências |

A **tabela** é criada pelas migrações (`db/migrations/004_bronze.sql` e `005_bronze_tabela_unica.sql`), não por estes arquivos.

## Validações (`validar.py`)
Linhas na bronze = soma dos arquivos · linhas do Brasil = 11.621 · nenhuma linha do Brasil veio do arquivo dos outros países · cada conversa com texto tem 2 × turnos mensagens · total = 837.989.

## Para conferir no DBeaver
```sql
SELECT arquivo_origem, count(*) FROM bronze.wildchat GROUP BY 1;            -- 11.621 e 826.368
SELECT arquivo, linhas, left(sha256, 12) FROM ops.bronze_lote ORDER BY id DESC LIMIT 2;
SELECT * FROM bronze.wildchat WHERE country = 'Brazil' LIMIT 5;             -- o dado cru
```

## Limites
Duplicatas e valores vazios continuam aqui (a limpeza é da Silver). A coluna `primeira_resposta_ts` foi calculada ao gerar a semente (`etl/semente/make_seed.py`); o resto é cópia fiel.
