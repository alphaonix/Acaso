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
Opção 3. `docker compose up` lê a semente versionada em `data/seed/`. O caminho do dado bruto até a semente é um **comando oficial e opcional**:
`docker compose --profile base run --rm baixar-base` (`etl/semente/baixar_base.py`) baixa o WildChat-1M do Hugging Face, gera a semente e confere as contagens.

## Atualização (16/11/2026): a opção 1 voltou a ser possível, mas continua sendo a segunda escolha
- A base **não exige mais login**: a página do dataset no Hugging Face está pública (`gated: false`), então o motivo "exige aceitar termos e token" caiu. O script fixa a revisão do dataset (`7d6490e4…`) para o download ser sempre o mesmo.
- **Medido:** baixar 1 dos 14 arquivos (231 MB) levou **533 s** nesta máquina; os 14 levariam cerca de 2 horas. Para quem avalia, o primeiro `up` dependeria da internet e do Hugging Face; hoje ele leva 2 a 3 minutos e não depende de nada externo para os dados.
- **Verificado:** a semente regenerada a partir do arquivo bruto completo é **idêntica byte a byte** (sha256) à do repositório; lida em vários arquivos, o conteúdo e a ordem são os mesmos (a divisão interna em blocos pode mudar os bytes, e então o ETL recarrega, sem mudar nenhum número).
- **Decisão:** a semente continua no repositório como padrão (rápido e à prova de falha de rede); o `baixar-base` prova que ela é reproduzível a partir da fonte.
- **O banco guarda os dados** entre um `up` e outro: o ETL só roda se o banco estiver vazio, se a semente mudou (sha256) ou sob `--recarregar`.

## Consequências
- Países além do Brasil não têm tema, recusa nem tamanhos (sem texto): a tela diz "indisponível".
- Conversas com país nulo entram como "Desconhecido" e não somem em silêncio.
- **Licença (conferida em 12/11/2026):** a página do WildChat-1M no Hugging Face declara **`odc-by`** (Open Data Commons Attribution). A licença permite usar e redistribuir
  **com atribuição**, que consta no README (fonte, Allen Institute for AI, e a citação do artigo). A página não traz portão de acesso nem condição adicional.
- **Ponto ainda aberto, de privacidade:** a semente do Brasil contém o texto das conversas (já anonimizado pelo WildChat, mas pode haver dado
  pessoal). A licença permite redistribuir, mas isso não elimina o risco de privacidade. Decisão: repositório **privado**, com acesso dado só a quem avalia.
  Registrado como risco (seção 4.3 do documento, `docs/RISCOS.md`).