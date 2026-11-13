# Onde cada exigência do PDF foi atendida

Mapa da seção do PDF (Desafio Técnico Acaso) para o artefato do repositório. ✔ feito · ◐ feito com ressalva (dita ao lado) · ✘ aberto.
Prazo: 16/11/2026, 23h59.

## Entrega (seções 1 a 3) e restrições (2.2 e 2.3)
| Exigência | | Onde |
|---|---|---|
| Repositório com instruções e ADRs e BDRs (contexto, opções, escolha) | ✔ | [`README.md`](README.md), [`docs/adr/`](docs/adr), [`docs/bdr/`](docs/bdr) |
| Sobe do zero com um comando, carrega a base analítica **a partir do bruto**, mostra 2+ telas com dados reais | ◐ | `docker compose up --build`; 5 telas. O "bruto" é a **semente** gerada da base completa (ADR-002), porque os 3 GB não cabem no GitHub; o caminho do bruto completo está em `etl/download_full.py` e `etl/make_seed.py` |
| Frontend, backend e base analítica | ✔ | `frontend/`, `backend/`, `db/` e `etl/` (Postgres em camadas: bronze, silver, gold) |
| O dashboard **não lê a base bruta** | ✔ | A API usa um papel somente leitura que só enxerga a gold e o `ops` (`db/migrations/002`) |
| Documento curto com achados e decisões e parágrafo de uso de IA | ◐ | [`docs/DOCUMENTO.md`](docs/DOCUMENTO.md); **faltam as horas** no parágrafo de IA |
| AWS: infraestrutura, custo e LLM; descrever a implantação | ◐ | [`infra/README.md`](infra/README.md): diagrama, custo (≈ US$ 136/mês), sem LLM; o Terraform passa em `validate` e **não foi aplicado** |
| O que o dashboard mostra e **nunca mostra** | ✔ | Tela "Glossário e qualidade"; [`docs/arquitetura.md`](docs/arquitetura.md) |
| Cada premissa registrada, com o que muda se estiver errada | ✔ | [`docs/bdr/BDR-001`](docs/bdr/BDR-001-usuario-sessao-retorno.md) e [`docs/SENSIBILIDADE.md`](docs/SENSIBILIDADE.md) (reproduzível) |
| Análise sobre `country = 'Brazil'` | ✔ | Efeitos e decomposição são do Brasil; o painel tem seletor de país |

## 3.1 Discovery e EDA
| Exigência | | Onde |
|---|---|---|
| Definições de usuário, sessão, 1ª experiência e retorno + quanto o resultado muda | ✔ | BDR-001, `docs/SENSIBILIDADE.md` (o gap da sessão é a premissa que mais pesa: 19,6% a 26,3%) |
| Variáveis da 1ª experiência e como cada uma é derivada | ◐ | [`docs/COMO_FUNCIONA.md`](docs/COMO_FUNCIONA.md), [`BDR-003`](docs/bdr/BDR-003-classificacao-de-tema.md). Tema e recusa são **regras**, sem IA; a **conferência manual está pendente** |
| Problemas de qualidade e como foram tratados | ✔ | Tela "Glossário e qualidade" (11 problemas, números reais) e BDR-001 |
| EDA com padrões, concentrações e anomalias | ✔ | [`docs/EDA.md`](docs/EDA.md): 7 figuras, cada uma com a conclusão e o que fazer (retorno rápido, GPT-4 some de jul a out/2023, 20 pessoas = 39% do volume, uso noturno e de fim de semana, dispositivo, efeitos por modelo, idioma); resumo em `docs/DOCUMENTO.md` §3; figuras reproduzíveis em `analise/06_eda_figuras.py` |
| O que os dados permitem medir, não permitem e o que falta | ✔ | `docs/DOCUMENTO.md` §4 |
| Sugestões para o assistente e para o dashboard | ✔ | `docs/DOCUMENTO.md` §5 e `docs/EDA.md` (7 indicadores ou telas novos e 4 sugestões ao produto; **6 deles já estão no painel**: curva e voltou em 24 h na tela Coortes, estratos por modelo, dispositivo e idioma em "O que faz voltar", o resto na Visão geral) |

## 3.2 Análise
| Exigência | | Onde |
|---|---|---|
| Efeito de cada fator com IC, **ordenado pelo tamanho** | ✔ | Tela "O que faz voltar"; [`BDR-004`](docs/bdr/BDR-004-analise-de-efeitos.md) (AIPW, E-value, correção para 16 testes) |
| Fatores de confusão, grupos semelhantes, o que prova e o que não prova | ✔ | BDR-004 e `docs/DOCUMENTO.md` §4 |
| Uma semana que mudou: perfil ou taxa (mix × taxa) | ◐ | Feito por **mês** (padrão: mai./2023 → abr./2024, de 22,3% para 21,1%: mix +2,2 pp, taxa −2,0 pp, interação −1,5 pp, sem diferença além do ruído); a semana tem só 40 a 90 elegíveis. Tela "Coortes semanais" |
| Três achados com a decisão de cada um | ◐ | `docs/DOCUMENTO.md` §4; os achados 1 e 2 dependem da validação de tema e recusa |

## 3.3 Dashboard (documentação)
| Exigência | | Onde |
|---|---|---|
| Telas: pergunta, gráficos e por quê | ✔ | `docs/arquitetura.md` (Telas) |
| Indicadores: definição, fórmula, denominador, período, SQL, comportamento com amostra pequena | ✔ | [`docs/INDICADORES.md`](docs/INDICADORES.md) (gerado do catálogo que alimenta a tela); taxas com menos de 30 elegíveis aparecem como "amostra pequena" |
| Arquitetura: fluxo com diagrama, AWS, stack, modelo da base, endpoints | ✔ | `docs/arquitetura.md`, `infra/README.md` |
| Outros países: idioma, fuso, comparação | ◐ | Implementado (seletor de 202 países, PT/EN, comparação com a média geral); o **fuso** só está mapeado para ~40 países, os demais usam UTC e aparecem como "aproximado" |
| Performance: pré-calculado, cache, expiração, medição | ◐ | Tudo pré-calculado na gold; p95 medido de 7 a 22 ms. O **cache está desenhado, não implementado** (20 ms dispensa) |

## 4 Sustentação
| Exigência | | Onde |
|---|---|---|
| 4.1 O que registrar em cada camada; perceber divergência; testes; como a mudança chega à produção | ✔ | [`docs/TESTES.md`](docs/TESTES.md) (93 testes, 53 conferências por carga, prova por mutação, fluxo de mudança), `ops.qa_resultado`, schema `auditoria`, logs JSON da API |
| 4.2 Incidente (as 5 respostas) | ✔ | [`docs/INCIDENTE.md`](docs/INCIDENTE.md); o teste dourado está em `etl/tests/test_incidente.py` |
| 4.3 Riscos e decisões em aberto | ✔ | [`docs/RISCOS.md`](docs/RISCOS.md) |

## As armadilhas do enunciado, uma por uma
1. **`timestamp` é o último turno, não o início:** o início é a 1ª resposta do assistente (`primeira_resposta_ts`); testado em `test_incidente.py`.
2. **`conversation_hash` não é chave única:** só a cópia exata (hash + IP + início) é removida; o mesmo hash com IP ou início diferente é outra conversa.
3. **Não há ID de usuário; IP compartilhado:** usuário = IP + família do navegador/sistema, sem versão; sensibilidade medida (só IP: 23,7%; user-agent completo: 26,2%).
4. **Censura à direita e à esquerda:** elegível = 1ª vez 30 dias depois do início dos dados e 7 dias antes do fim.
5. **O retorno exclui a própria sessão:** sessão nova só se passam mais de 30 minutos do fim da conversa anterior.
6. **Fuso:** o dia e a semana contam em America/Sao_Paulo (UTC no banco).
7. **Documento curto:** o detalhe vai para ADRs, BDRs e `docs/`; o documento é `docs/DOCUMENTO.md`.
8. **Multi-país é desenho e plus:** implementado como plus, sem tirar o foco do Brasil.

## O que ainda está aberto
1. **Precisão de tema e recusa** (regras de palavras): amostras prontas em `exports/amostra_validacao_*.csv` (local, fora do Git); falta a conferência manual e o cálculo da precisão. Afeta os achados 1 e 2.
2. **Horas do parágrafo de IA** em `docs/DOCUMENTO.md` (§8).
3. **Rodadas 5 a 9 do `docs/VALIDACAO.md`** (conferência dos números no DBeaver), dos três cartões novos (conversas, turnos médios, uso de GPT-4) e das métricas ampliadas (curva, concentração, uso por hora, recusa por versão, estratos, dispositivo, idioma × navegador). Elas ainda **não** estão no portão de qualidade: só entram depois da conferência.
4. **AWS:** o Terraform é esboço (`validate` ok, sem `plan`/`apply`); o preço do RDS vem de fonte secundária.
5. **Fuso** de ~160 países, **cache** e **SSO** são extensões, descritas e não implementadas.
6. **Tema e recusa fora do Brasil:** a semente só tem o texto das conversas do Brasil e as regras de palavras são em português. Retorno, modelo por versão, uso, horário e concentração já valem para todos os países; tema e recusa pedem o texto completo (`etl/download_full.py`) e regras por idioma, com validação própria.
7. **Países pequenos:** a Visão geral troca o gráfico semanal pelo mensal quando quase nenhuma semana alcança 30 elegíveis.
