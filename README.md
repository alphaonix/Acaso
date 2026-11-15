# Retenção de um assistente de IA: análise e dashboard

Desafio técnico (Acaso): **o que faz quem experimentou o assistente voltar a usá-lo em até 7 dias**, com o efeito de cada fator, a incerteza e a separação entre causa e seleção.
Base: WildChat-1M (análise sobre `country = 'Brazil'`; o dashboard tem filtro de país).

**Resultado em uma linha:** no Brasil, **23,7% voltam em até 7 dias** (IC 95%: 22,0% a 25,5%). Quem abre a conversa só com uma saudação volta ~8 pp menos e quem recebe uma recusa na primeira resposta, ~10 pp menos;
trocar de modelo ou alongar a resposta não mostra ganho. É associação ajustada, não prova de causa.

## Como subir do zero
Requisitos: Docker e Docker Compose (não precisa de Python nem de baixar a base).
```bash
docker compose up --build
```
Tela: http://localhost:3000 · API (documentação): http://localhost:8000/docs · banco: `localhost:5433`.
A carga (cerca de 1,5 minuto) lê a semente em `data/seed/`, monta a base analítica, estima os efeitos, **confere os números** e termina; depois sobem a API e a tela.
Se uma conferência falhar, a carga é revertida e nada é publicado. Depois de mudar o código, use sempre `--build`. Para apagar o banco: `docker compose down -v`.

**Acesso (nenhuma senha fica no repositório).** Sem configurar nada, existe a conta `avaliacao@exemplo.com`, com **senha aleatória gerada na primeira subida e mostrada uma vez no log**:
```bash
docker compose logs etl | findstr SENHA      # Windows
docker compose logs etl | grep SENHA          # Linux e macOS
```
Para usar o seu e-mail e senha: copie `.env.example` para `.env`, preencha `DASH_USERS` e `DASH_PASSWORD` e suba de novo com `--build`.

**As 4 telas:** Visão geral · O que faz voltar (efeitos com intervalo) · Coortes semanais (inclui "chegou gente diferente × a mesma gente voltou diferente") · Ajuda.
Seletor de país, idioma (PT/EN) e tema (claro/escuro) no cabeçalho; o botão "i" de cada indicador mostra a definição e a fórmula.

## Testes
```bash
docker compose --profile test run --rm --build testes-etl          # regras da definição, limpeza, gold, incidente do PDF, proteções
docker compose --profile test run --rm --build testes-api          # decomposição mix × taxa
docker compose --profile test run --rm --build testes-integracao   # API × Gold (precisa do banco carregado)
```
Detalhes em [`docs/TESTES.md`](docs/TESTES.md).

## Onde ler o quê
| Para | Abra |
|---|---|
| **Resultado**: achados, decisões, riscos, uso de IA | [`docs/DOCUMENTO.md`](docs/DOCUMENTO.md) |
| Onde cada exigência do PDF foi atendida | [`REQUISITOS.md`](REQUISITOS.md) |
| Exploração dos dados (7 conclusões com figuras) | [`docs/EDA.md`](docs/EDA.md) |
| Como o dado vira número, com consultas para conferir | [`docs/COMO_FUNCIONA.md`](docs/COMO_FUNCIONA.md) |
| **Conferir qualquer número da tela em SQL** (15 consultas comentadas, para qualquer país) | [`docs/CONFERIR_NUMEROS.md`](docs/CONFERIR_NUMEROS.md) |
| Incidente da seção 4.2 · riscos da 4.3 | [`docs/INCIDENTE.md`](docs/INCIDENTE.md) · [`docs/RISCOS.md`](docs/RISCOS.md) |
| Arquitetura, endpoints e telas · AWS e custo | [`docs/arquitetura.md`](docs/arquitetura.md) · [`infra/README.md`](infra/README.md) |
| Como evitar e investigar divergências de número | [`docs/PREVENCAO_DE_DIVERGENCIAS.md`](docs/PREVENCAO_DE_DIVERGENCIAS.md) |
| Cada camada (Bronze → Silver → Gold) em detalhe | [`etl/LEIA-ME.md`](etl/LEIA-ME.md) e [`docs/CAMADAS_BRONZE_A_GOLD.md`](docs/CAMADAS_BRONZE_A_GOLD.md) |
| Decisões | ADR [001](docs/adr/ADR-001-stack-e-monorepo.md) · [002](docs/adr/ADR-002-semente-do-bruto-no-repositorio.md) · [003](docs/adr/ADR-003-base-analitica.md) · [004](docs/adr/ADR-004-arquitetura-em-camadas.md) · [005](docs/adr/ADR-005-auditoria-e-linhagem.md) — BDR [001](docs/bdr/BDR-001-usuario-sessao-retorno.md) · [002](docs/bdr/BDR-002-principios-do-dashboard.md) · [003](docs/bdr/BDR-003-classificacao-de-tema.md) · [004](docs/bdr/BDR-004-analise-de-efeitos.md) |

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `data/seed/` | Semente da base bruta (Brasil com texto + demais países só com metadados) |
| `etl/` | A carga: `main.py` chama bronze → silver → gold e confere cada uma. Comece por [`etl/LEIA-ME.md`](etl/LEIA-ME.md) |
| `db/migrations/` | Esquema da base analítica e o papel somente leitura da API |
| `backend/` | API FastAPI (lê só a gold) e testes |
| `frontend/` | Dashboard Next.js, PT/EN, tema claro e escuro |
| `analise/` | Scripts da análise (sensibilidade, figuras da EDA, exportação para Power BI) |
| `docs/` | Documento da entrega, ADRs, BDRs, EDA, indicadores, testes, incidente, riscos |
| `infra/` | Implantação na AWS: desenho, custo e esboço em Terraform |

## Explorar as camadas no DBeaver
`localhost:5433`, banco `retencao`, usuário `auditor`, senha `auditor` (somente leitura).
`bronze.wildchat` é a cópia do bruto (uma tabela, todos os países); `silver.fato_conversa` e `silver.fato_usuario` são as camadas limpas, sem texto; `gold.*` é o que a tela lê.
Para auditar uma pessoa passo a passo: `SELECT * FROM auditoria.audite_usuario('00a3cf656f92');`.

## Dados, licença e privacidade
- **Fonte:** [WildChat-1M](https://huggingface.co/datasets/allenai/WildChat-1M) (Allen Institute for AI), licença **ODC-By**, com atribuição. Citação: Zhao et al., *WildChat: 1M ChatGPT Interaction Logs in the Wild*, ICLR 2024.
- **Privacidade:** a semente do Brasil leva o texto das conversas, por isso este repositório deve ser **privado**. O dashboard **nunca mostra** texto, IP (nem com hash), user-agent nem identificador de usuário, e a base analítica não guarda texto.
- **Marca:** os logotipos da Acaso em `frontend/public/` são usados só para o dashboard desta avaliação.

## O que ainda depende de conferência humana
Tema e recusa vêm de regras de palavras e a precisão ainda não foi medida na amostra manual (BDR-003); os achados 1 e 2 dependem disso. O Terraform passa em `validate`, mas não foi aplicado. Lista completa em [`REQUISITOS.md`](REQUISITOS.md#o-que-ainda-está-aberto).

**Problema de build com `SSL: UNEXPECTED_EOF`** em `files.pythonhosted.org`: é rede (VPN ou proxy), não o projeto. Tente outra rede.
