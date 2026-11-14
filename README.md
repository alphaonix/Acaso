# Retenção de um assistente de IA: análise e dashboard

Desafio técnico (Acaso): **o que faz quem experimentou o assistente voltar a usá-lo em até 7 dias**, com o efeito de cada fator, a incerteza e a separação entre causa e seleção.
Base: WildChat-1M (análise sobre `country = 'Brazil'`; o dashboard tem filtro de país, com 202 países).

**Resultado em uma linha:** no Brasil, **23,7% voltam em até 7 dias** (IC 95%: 22,0% a 25,5%). Quem abre a conversa só com uma saudação volta ~8 pp menos e quem recebe uma recusa na primeira resposta, ~10 pp menos;
trocar de modelo ou alongar a resposta não mostra ganho. É associação ajustada, não prova de causa.

## Comece por aqui
| Para | Abra |
|---|---|
| **Ler o resultado** (achados, decisões, riscos, uso de IA) | [`docs/DOCUMENTO.md`](docs/DOCUMENTO.md) |
| Ver **onde cada exigência do PDF foi atendida** | [`REQUISITOS.md`](REQUISITOS.md) |
| **Explorar os dados:** sete conclusões com figuras, intervalos e sugestões | [`docs/EDA.md`](docs/EDA.md) |
| Entender **como o dado vira o número**, passo a passo, com consultas de conferência | [`docs/COMO_FUNCIONA.md`](docs/COMO_FUNCIONA.md) |
| **Validar cada camada** (Bronze → Silver → Gold): o que cada código faz, por quê, limites e conciliação de ponta a ponta | [`docs/CAMADAS_BRONZE_A_GOLD.md`](docs/CAMADAS_BRONZE_A_GOLD.md) |
| O incidente da seção 4.2 e os riscos da 4.3 | [`docs/INCIDENTE.md`](docs/INCIDENTE.md) · [`docs/RISCOS.md`](docs/RISCOS.md) |
| Arquitetura, endpoints e telas | [`docs/arquitetura.md`](docs/arquitetura.md) |
| Implantação na AWS, custo e Terraform | [`infra/README.md`](infra/README.md) |

## Como subir do zero
Requisitos: Docker e Docker Compose. Não precisa de Python nem de baixar a base.
```bash
docker compose up --build
```
**Depois de mudar o código, use `docker compose up --build`.** Sem o `--build`, o Compose reaproveita as imagens antigas e a tela
(ou a API) continua na versão anterior. Para derrubar e apagar o banco: `docker compose down -v`.

Tela: http://localhost:3000 · API (documentação): http://localhost:8000/docs · banco: `localhost:5433`.
A carga (cerca de 1,5 minuto) lê a semente em `data/seed/` (ADR-002), popula a base analítica em camadas, estima os efeitos, **confere os números** (53 conferências) e termina; depois sobem a API e a tela.
Se uma conferência falhar, a carga é revertida e nada é publicado.

**Acesso (nenhuma senha fica no repositório).** Sem configurar nada, existe a conta `avaliacao@exemplo.com`, com uma **senha aleatória gerada na primeira subida e mostrada uma única vez no log**:
```bash
docker compose logs etl | findstr SENHA      # Windows (PowerShell/cmd)
docker compose logs etl | grep SENHA          # Linux e macOS
```
Para usar o seu e-mail e a sua senha, copie `.env.example` para `.env` e preencha `DASH_USERS` (`email|Nome|url-da-foto;email|Nome`; a foto é opcional) e `DASH_PASSWORD`; depois `docker compose up --build`.
Se perder a senha gerada: `docker compose down -v` e suba de novo (ou defina `DASH_PASSWORD`).
**O que você vai ver (4 telas):** Visão geral (cartão "de onde vêm os dados", 6 cartões, a história em 8 passos curtos, retorno por mês com intervalo, comparação entre modelos, curva de retorno, quando usam, modelo no tempo, concentração do uso e comparação de todos os países, com ranking só para quem tem 1.000+ elegíveis) ·
O que faz voltar (efeitos ordenados, com intervalo, os 4 achados, com o impacto estimado no retorno, e, no fim, dispositivo e idioma × navegador, **exploratório**) · Coortes semanais (curva de retorno com 24 h, 7 e 30 dias, pessoas novas por semana, mapa de calor (por semana ou por mês), decomposição "chegou gente diferente × a mesma gente voltou diferente") · Ajuda (para que serve o painel, palavras e regras, privacidade e problemas de qualidade dos dados).
Seletor de país, idioma (PT/EN) e tema (claro/escuro) no cabeçalho; o botão "i" de cada indicador mostra a definição e a fórmula.

## Testes (93)
```bash
docker compose --profile test run --rm --build testes-etl     # 64 testes das definições, num banco descartável
docker compose --profile test run --rm --build testes-api     # 29 testes da decomposição mix × taxa
```
Cobrem cada regra de borda da definição (sessão de 30 min, janela de 7 dias, elegibilidade, limpeza, tema, recusa) e **reproduzem o incidente** do PDF; detalhes e a prova por mutação em [`docs/TESTES.md`](docs/TESTES.md).
A sensibilidade das premissas (reproduzível) está em [`docs/SENSIBILIDADE.md`](docs/SENSIBILIDADE.md): `python analise/05_sensibilidade_definicoes.py` com o compose ativo.

## Explorar as camadas (DBeaver: `localhost:5433`, banco `retencao`, usuário `etl`, senha `etl`)
`bronze.wildchat` é UMA tabela com o WildChat-1M inteiro, como veio (todos os países; as linhas do Brasil trazem o texto das conversas em `conversation`, JSON, e `arquivo_origem` diz de qual arquivo da semente cada linha veio).
`silver.fato_conversa` e `silver.fato_usuario` são derivadas dela, sem texto. `gold.*` é o que a tela lê.
Para ver uma linha do bruto virar silver: `SELECT * FROM bronze.wildchat WHERE country = 'Brazil' LIMIT 20;` e depois `SELECT * FROM silver.fato_conversa WHERE conversation_hash = '<hash>';`.
Para auditar um usuário passo a passo: `SELECT * FROM auditoria.audite_usuario('00a3cf656f92');`.

**Linhagem entre camadas.** O schema `auditoria` (consulta no DBeaver; **não há tela no dashboard**, que é voltado ao cliente) mostra, a cada carga: conversas por camada (`auditoria.camadas`), o que foi excluído da bronze
para a silver (linha a linha, com o motivo), valores vazios antes e depois e exemplos de antes e depois (`docs/VALIDACAO.md`, rodada 7; decisão no ADR-005).

**Idioma e tema.** Para incluir outro idioma, crie `frontend/lib/idiomas/<codigo>.ts` com as mesmas chaves de `pt.ts` (o compilador acusa chave faltando) e acrescente-o em `lib/i18n.tsx`.
Os textos que vêm do banco (nomes de indicadores, fatores e conferências) são traduzidos em `lib/traducao-dados.ts`.

**Se o build falhar com `SSL: UNEXPECTED_EOF` em `files.pythonhosted.org`:** é rede (alguns ambientes desviam esse domínio), não o projeto. Tente outra rede, desligue VPN ou proxy, ou rode a API fora do Docker
(`pip install -r backend/requirements.txt`, `uvicorn app.main:app` com `DATABASE_URL` apontando para `localhost:5433`) e o frontend com `npm run build && npm start`.

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `data/seed/` | Semente da base bruta (Brasil completo, com texto + demais países só com metadados), gerada da base completa |
| `data/raw/` | Base bruta completa (3 GB), **fora do Git**; origem da semente (`etl/download_full.py`, `etl/make_seed.py`) |
| `etl/` | Carga bruta → analítica em camadas (`main.py`, `pipeline/`), estimativa dos efeitos, portão de qualidade e `tests/` |
| `db/migrations/` | Esquema da base analítica (bronze, silver, gold, ops, auditoria) e papel somente leitura da API |
| `backend/` | API FastAPI (lê só a gold e o `ops`) e `tests/` |
| `frontend/` | Dashboard Next.js (React, Recharts), PT/EN, tema claro e escuro |
| `analise/` | Scripts de discovery, sensibilidade, figuras da exploração (`06_eda_figuras.py`) e exportação para Power BI |
| `docs/` | Documento da entrega, `adr/` (decisões técnicas), `bdr/` (negócio e premissas), `COMO_FUNCIONA`, `EDA` (com `figuras/`), `INDICADORES`, `SENSIBILIDADE`, `TESTES`, `INCIDENTE`, `RISCOS`, `VALIDACAO` |
| `infra/` | Implantação na AWS: desenho, custo e esboço em Terraform |

## Decisões registradas
**ADR:** [001](docs/adr/ADR-001-stack-e-monorepo.md) stack · [002](docs/adr/ADR-002-semente-do-bruto-no-repositorio.md) semente da base bruta · [003](docs/adr/ADR-003-base-analitica.md) base analítica (Postgres) ·
[004](docs/adr/ADR-004-arquitetura-em-camadas.md) camadas e portão de qualidade · [005](docs/adr/ADR-005-auditoria-e-linhagem.md) auditoria e linhagem.
**BDR:** [001](docs/bdr/BDR-001-usuario-sessao-retorno.md) usuário, sessão e retorno (com a sensibilidade medida) · [002](docs/bdr/BDR-002-principios-do-dashboard.md) princípios do dashboard ·
[003](docs/bdr/BDR-003-classificacao-de-tema.md) tema e recusa · [004](docs/bdr/BDR-004-analise-de-efeitos.md) análise dos efeitos.

## Dados, licença e privacidade
- **Fonte:** [WildChat-1M](https://huggingface.co/datasets/allenai/WildChat-1M) (Allen Institute for AI), licença **ODC-By** (Open Data Commons Attribution): permite usar e redistribuir **com atribuição**, que está aqui.
  Citação: Zhao et al., *WildChat: 1M ChatGPT Interaction Logs in the Wild*, ICLR 2024.
- **Privacidade:** as conversas podem conter dado pessoal (o WildChat já anonimiza parte). A semente do Brasil leva o **texto das conversas**; por isso este repositório deve ser **privado**, com acesso só a quem avalia.
  O dashboard **nunca mostra** texto, IP (nem com hash), user-agent nem identificador de usuário, e a base analítica não guarda texto (ADR-002, ADR-004).
- **Marca:** os logotipos e o símbolo da Acaso em `frontend/public/` são usados só para o dashboard desta avaliação.

## O que ainda depende de conferência humana
Tema e recusa vêm de regras de palavras e **a precisão ainda não foi medida na amostra manual** (BDR-003); os achados 1 e 2 dependem disso. O Terraform passa em `validate`, mas não foi aplicado.
Lista completa e honesta em [`REQUISITOS.md`](REQUISITOS.md#o-que-ainda-está-aberto).
