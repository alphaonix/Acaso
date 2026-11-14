# ADR-002: como a base bruta chega a quem executa o projeto

Status: aceita (com um ponto aberto sobre privacidade do repositório).

## Contexto
O PDF exige que o dashboard "suba do zero com um comando e carregue a base analítica a partir da base bruta", e que o
envio seja por repositório. A base completa tem 3,3 GB (838 mil conversas): não cabe no GitHub (limite de 100 MB por
arquivo) e não pode depender de o avaliador rodar scripts Python à mão.

## Opções
1. Container que baixa do Hugging Face no `up`. Exige aceitar termos e token; 3 GB; frágil e lento.
2. Git LFS com a base completa. Cota de banda do LFS e 3 GB de clone.
3. **Semente versionada**: Brasil bruto completo (22 MB, com texto) + demais países só com metadados (35 MB, sem texto).

## Medição
Brasil completo 22,2 MB; outros países sem texto 35,3 MB (826.368 linhas, inclui 1.060 com país nulo); com 300
caracteres de texto por conversa seriam 190 MB (não cabe). Total 11.621 + 826.368 = 837.989, igual à base.

## Decisão
Opção 3. `etl/semente/make_seed.py` gera `data/seed/*.parquet` a partir da base completa (`data/raw/`, fora do Git).
`docker compose up` lê a semente. O download completo continua disponível em `etl/semente/download_full.py`.

## Consequências
- Países além do Brasil não têm tema, recusa nem tamanhos (sem texto): a tela diz "indisponível".
- Conversas com país nulo entram como "Desconhecido" e não somem em silêncio.
- **Licença (conferida em 12/11/2026):** a página do WildChat-1M no Hugging Face declara **`odc-by`** (Open Data Commons Attribution). A licença permite usar e redistribuir
  **com atribuição**, que consta no README (fonte, Allen Institute for AI, e a citação do artigo). A página não traz portão de acesso nem condição adicional.
- **Ponto ainda aberto, de privacidade:** a semente do Brasil contém o texto das conversas (já anonimizado pelo WildChat, mas pode haver dado
  pessoal). A licença permite redistribuir, mas isso não elimina o risco de privacidade. Decisão: repositório **privado**, com acesso dado só a quem avalia.
  Registrado como risco (seção 4.3 do documento, `docs/RISCOS.md`).