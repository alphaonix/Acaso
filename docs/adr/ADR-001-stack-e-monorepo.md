# ADR-001: stack e repositório único

Status: aceita.

## Contexto
O PDF pede frontend, backend e base analítica, que subam com um comando e possam ser explicados em entrevista.

## Opções
1. **Next.js full-stack.** Menos peças, mas mistura regra de negócio com tela e deixa a estatística fora da API.
2. **Streamlit ou Dash.** Rápido, mas não mostra frontend e backend separados nem controle de UX.
3. **Next.js + FastAPI + Postgres + ETL em Python.** Separa responsabilidades e reaproveita o código da análise.

## Decisão
Opção 3, em um repositório só: `etl/`, `backend/`, `frontend/`, `db/`, `docs/`, `analise/`, `infra/`.
- Frontend: Next.js e TypeScript.
- Backend: FastAPI.
- ETL: Python, com DuckDB só para ler os Parquet e SQL do Postgres para transformar. Os efeitos são estimados com scikit-learn e scipy.
- Base analítica: Postgres.

## Consequências
- Quatro serviços no compose (db, etl, api, web): mais configuração, fronteiras claras.
- A estatística roda no ETL, não a cada requisição. A tela só lê o resultado, com intervalo de confiança.
