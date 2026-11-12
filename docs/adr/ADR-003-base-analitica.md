# ADR-003: base analítica em PostgreSQL

Status: aceita. A organização em camadas está no ADR-004 (substitui o schema único do primeiro esqueleto).

## Contexto
O dashboard não lê a base bruta; lê uma base analítica "desenhada e populada" por nós. Precisa de consultas rápidas,
de privacidade (sem texto de conversa) e de definições rastreáveis.

## Opções
1. DuckDB em arquivo (simples e muito rápido; menos parecido com produção, pouco controle de acesso por papel).
2. S3 Parquet + Athena (barato em escala; latência de segundos e custo por consulta, ruim para tela interativa).
3. **PostgreSQL** (RDS na AWS): índices, papéis de acesso por schema, mesmo motor local e em produção.

## Decisão
PostgreSQL para silver e gold (`db/migrations/001_schema_em_camadas.sql`); DuckDB só dentro do ETL, para transformar os
Parquet antes de gravar. Silver e gold guardam **variáveis derivadas, nunca texto**. Os agregados e o catálogo de
indicadores (definição, fórmula, denominador, SQL e fonte; BDR-002) são pré-calculados e gravados no gold.

## Consequências
- O ETL é a única fonte de verdade das definições (BDR-001/003); mudá-las exige nova carga e atualizar o portão de qualidade.
- Reprocessar do zero leva cerca de um minuto neste volume (837 mil conversas).
