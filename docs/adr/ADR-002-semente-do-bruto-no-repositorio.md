# ADR-002: como a base bruta chega a quem executa o projeto

Status: aceita.

## Contexto
O PDF pede que o dashboard suba do zero com um comando e que o envio seja por repositório. A base completa tem 3,3 GB (838 mil conversas): não cabe no GitHub (100 MB por arquivo) e o avaliador não deve rodar scripts à mão.

## Opções
1. **Baixar do Hugging Face no `up`.** Depende da internet e do Hugging Face; medi 533 s para 1 dos 14 arquivos (231 MB), cerca de 2 horas para todos.
2. **Git LFS com a base completa.** Cota de banda do LFS e 3 GB de clone.
3. **Semente versionada.** Brasil completo, com texto (22 MB), e os demais países só com metadados, sem texto (35 MB).

## Decisão
Opção 3: `docker compose up` lê a semente em `data/seed/`. A base bruta chega a ela por um comando opcional, `docker compose --profile base run --rm baixar-base` (`etl/semente/baixar_base.py`). Ele baixa o WildChat-1M com a revisão fixada, gera a semente e confere as contagens (837.989 e 11.621).
- A semente regenerada a partir da fonte é idêntica, byte a byte (sha256), à do repositório. Lida em vários arquivos, o conteúdo e a ordem são os mesmos.
- O primeiro `up` leva cerca de 3 minutos (ETL, medido: 167 s) e não depende de rede para os dados.
- O banco guarda os dados entre um `up` e outro: o ETL só roda se o banco estiver vazio, se a semente mudou (sha256) ou com `--recarregar`.

## Consequências
- Fora do Brasil não há tema, recusa nem tamanhos (sem texto): a tela diz "indisponível".
- Conversas sem país entram como "Desconhecido".
- **Licença:** o WildChat-1M declara `odc-by` no Hugging Face (acesso público, sem login). A redistribuição exige atribuição, que está no README (Allen Institute for AI e a citação do artigo).
- **Privacidade:** a semente do Brasil tem o texto das conversas, já anonimizado pelo WildChat, mas pode conter dado pessoal. O repositório será **público**, porque a fonte já é pública; o risco foi aceito e está em `docs/RISCOS.md`. A base analítica não guarda texto, e o painel nunca mostra texto, IP nem identificador de pessoa.
