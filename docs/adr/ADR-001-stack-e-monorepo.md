# ADR-001: stack e repositório único

Status: aceita.

## Contexto
O PDF exige dashboard com frontend, backend e base analítica, que suba com um comando e seja explicável em entrevista.
A pessoa da vaga "faz o discovery, a análise e o dashboard (frontend e backend)" e responde pelos números.

## Opções
1. **Next.js full-stack** (rotas de API no próprio Next, como no código de referência do incidente). Menos peças;
   mistura regra de negócio com UI; a estatística (statsmodels) ficaria fora da API.
2. **Streamlit/Dash.** Rápido, mas não demonstra frontend e backend separados nem controle de UX para público não técnico.
3. **Next.js (frontend) + FastAPI (backend) + Postgres + ETL em Python/DuckDB.** Separa responsabilidades e reaproveita
   o código da análise em Python.

## Decisão
Opção 3, em um único repositório (monorepo): `etl/`, `backend/`, `frontend/`, `db/`, `docs/`, `analise/`, `infra/`, `tests/`.
Frontend em Next.js/TypeScript; backend FastAPI (contrato OpenAPI); ETL com DuckDB para as transformações pesadas e
statsmodels para os efeitos; Postgres como base analítica.

## Consequências
- Quatro serviços no compose (db, etl, api, web); mais configuração, mas fronteiras claras e testáveis.
- O cálculo estatístico roda no ETL, não por requisição: a tela só lê resultados com IC.
