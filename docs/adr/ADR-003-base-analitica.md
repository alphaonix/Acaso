# ADR-003: base analítica em PostgreSQL

Status: aceita. As camadas estão no ADR-004.

## Contexto
O dashboard não lê a base bruta, e sim uma base analítica criada por nós. Ela precisa de consulta rápida, de privacidade (sem texto de conversa) e de definições rastreáveis.

## Opções
1. **DuckDB em arquivo.** Simples e rápido, mas pouco parecido com produção e sem controle de acesso por papel.
2. **S3 Parquet + Athena.** Barato em escala, mas com latência de segundos e custo por consulta.
3. **PostgreSQL (RDS na AWS).** Índices, papéis por schema e o mesmo motor local e em produção.

## Decisão
Opção 3. Silver e gold ficam no Postgres e guardam **variáveis derivadas, nunca texto**. Os agregados e o catálogo de indicadores (definição, fórmula, denominador, SQL e fonte) são calculados na carga e gravados na gold. O DuckDB só lê os Parquet.

## Consequências
- O ETL é a única fonte das definições (BDR-001 e BDR-003). Mudar uma definição exige nova carga e atualizar as conferências.
- Reconstruir tudo do zero leva cerca de 3 minutos (837 mil conversas).
