# ADR-005: auditoria e linhagem entre camadas

Status: aceita (12/11/2026).

## Contexto
O PDF (4.1) pede saber, para cada camada, o que registrar para investigar um número errado. É preciso ver quantas linhas há em cada camada, o que foi excluído e por quê, os vazios e o antes e depois de cada tratamento.

## Opções
1. **Consultar bronze e silver direto.** Serve a quem usa SQL; a API não pode ler essas camadas (têm texto).
2. **Schema `auditoria` preenchido pelo ETL.** Guarda só contagens, nomes de coluna e identificadores técnicos.
3. **Ferramenta de linhagem** (OpenLineage, dbt docs, Great Expectations). Mais robusta, com mais peças.

## Decisão
Opção 2.
- **Linhagem por linha:** `silver.fato_conversa.bronze_id` aponta a linha da bronze de onde cada conversa veio.
- **Schema `auditoria`**, só com a última carga (o histórico fica em `ops.etl_execucao` e `ops.qa_resultado`):
  - `camadas`: conversas em cada camada, com excluídas e conferência (`confere`);
  - `fluxo_pais`: o funil bronze, excluídas, silver e gold, por país;
  - `nulos`: vazios antes e depois, com a ação (preenchido, mantido, excluído, derivado, não usado);
  - `registro_excluido`: as linhas excluídas, com o motivo e a linha que ficou no lugar;
  - `antes_depois`: exemplos em `campo=valor`, sem texto nem IP.
- **Conferências por transição:** as 66 de `ops.qa_resultado` dizem qual passagem protegem (bronze x arquivos, bronze para silver, silver, silver para gold, efeitos, números validados). A principal é **linhas da bronze = conversas da silver + excluídas**.
- **Sem tela no dashboard:** o painel é para o cliente, que não precisa dela. A API só lê `ops` (saúde e qualidade), não `auditoria`. A consulta é no DBeaver (README, seção 6).

## Consequências
- A auditoria guarda só a última carga e conta a **mesma unidade (conversas)** em cada camada; somar linhas de tabelas de granularidades diferentes não serve.
- Privacidade: das linhas excluídas guarda o número da linha e o hash da conversa. Nunca texto, IP, navegador nem identificador de pessoa.
- A auditoria roda na transação da carga: se a carga for cancelada, ela também não é gravada.
