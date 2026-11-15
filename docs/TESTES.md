# Testes automatizados

Objetivo (PDF 4.1): **a definição de um indicador não pode mudar sem ninguém perceber.** Os testes fixam cada regra de borda da
definição (BDR-001) e reproduzem o incidente do PDF (seção 4.2). São 155 testes de unidade (rodam em segundos, **não tocam o banco real**) e 20 de integração API × Gold (rodam contra o banco já carregado, **só leem**).

```bash
docker compose --profile test run --rm --build testes-etl     # 126 testes: sessão, retorno, elegibilidade, limpeza, tema, recusa, gold, catálogo, incidente, análise ampliada, prevenção de divergências, trava de escrita e integridade
docker compose --profile test run --rm --build testes-api     # 29 testes: decomposição mix x taxa
docker compose --profile test run --rm --build testes-integracao   # 20 testes: API x Gold e camadas entre si (precisa do banco carregado)
docker compose --profile test run --rm --build relatorio-fluxo      # gera exports/fluxo_dos_dados.html (caminho do dado + todas as conferências)
```
O perfil `test` não sobe com `docker compose up`. Os testes do ETL criam um banco descartável (`retencao_teste`) no mesmo servidor,
aplicam as migrações, inserem conversas **sintéticas** na bronze, rodam a silver e a gold de verdade e conferem o resultado; cada teste
termina em `ROLLBACK` e o banco é apagado no fim.

## O que cada arquivo garante
| Arquivo | Regra fixada |
|---|---|
| `test_sessao_retorno.py` | gap de 30 min (30 min exatos = mesma sessão; 30 min e 1 s = nova); retorno em até 7 dias (7 dias exatos conta; +1 s não); a própria sessão da 1ª experiência não é retorno; elegibilidade (30 dias do início e 7 dias do fim, nas duas bordas); 1ª experiência = 1ª conversa; semana, hora e dia no fuso do país |
| `test_incidente.py` | **teste dourado do incidente**: atualizar o navegador não cria outro usuário; a "primeira vez" é o início da conversa e não o último turno (em UTC); uma conversa longa não é retorno; reproduz na gold o cenário "5 usuários voltam com o Chrome atualizado" e exige 5 novos e 5 retornos, **nenhum "novo" fantasma** |
| `test_limpeza.py` | cópia exata excluída (e só ela); mesmo hash com IP ou início diferente é outra conversa; sem IP ou sem início excluída; país vazio vira "Desconhecido"; **bronze = silver + excluídas**; cada conversa aponta para a linha da bronze |
| `test_variaveis.py` | navegador e sistema sem versão (9 casos); tema do 1º pedido (11 casos); recusa só na abertura da resposta (7 casos); tema e recusa vazios fora do Brasil; duração e tamanhos |
| `test_gold.py` | intervalo de Wilson (valores conhecidos); amostra pequena esconde a taxa; taxa da semana (10 de 40 = 25%); a gold soma o que a silver tem |
| `test_acesso.py` | **nenhuma conta ou senha real no repositório**: sem configuração, uma conta genérica com senha aleatória (mostrada uma vez); a senha da primeira subida é mantida; com `.env`, a senha definida vale e contas fora da lista saem; a foto de perfil é opcional e só aceita https |
| `test_catalogo.py` | o **SQL de referência de cada indicador** (o que o glossário e `docs/INDICADORES.md` mostram) dá o mesmo número que a gold (inclui voltou em 24 h e 30 dias, concentração dos 10 mais ativos e recusa por versão): a fórmula documentada e a consulta executada não se separam (BDR-002) |
| `test_analise_ampliada.py` | **voltou em 24 h** (24 h exatas conta; +1 s não, mas conta em 7 dias) e `dias_ate_voltar`; voltou em 24 h implica voltou em 7 dias; **janela de 30 dias** nas duas bordas; a curva de retorno só usa quem tem janela completa e nunca decresce; idioma do navegador; fatores `idioma_x_navegador` e `dispositivo`; **concentração** por faixa e peso dos 10 mais ativos; **uso por hora no fuso do país** (01:30 UTC de quarta = 22:30 de terça em São Paulo); recusa, retorno e GPT-4 por versão do modelo e por mês; **país sem texto** tem retorno por versão e não tem recusa |
| `test_prevencao.py` | **o recálculo independente (Python, a partir da bronze) bate com a silver e pega um erro plantado** (voltou_7d, elegivel, voltou_24h); **contrato da semente** (coluna a menos, tipo trocado, coluna nova, arquivo ausente, e a semente real do repositório); **deriva** (sem carga anterior, mesma semente igual, mesma semente com mudança, semente nova só aponta variação grande, ignora carga que falhou, ignora medida nova); medidas por camada reprodutíveis e a impressão digital muda quando uma pessoa muda; o executor aceita função no lugar do SQL |
| `test_anomalia.py` | **a taxa salta e o sistema diz de onde veio**: carga igual e variação pequena não alertam; amostra pequena não é avaliada; 25% → 97% e queda são detectadas; origem **GOLD** (gold ≠ silver), **TRANSFORMAÇÃO** (mesma entrada, resultado diferente), **BRONZE** (60% das linhas sem endereço), **SILVER** (limpeza ou elegibilidade mudou) e **SEM CAUSA** (funil estável); "(vazio)" da bronze = "Desconhecido" da silver; a simulação aponta a camada onde o defeito foi plantado; grava em `auditoria.anomalia` |
| `etl/simulacao/` (não é pytest) | **teste ponta a ponta do detector de anomalia**: `docker compose --profile operacao run --rm simular-cenarios <cenarios>` (11 cenários: 3 que começam na bronze, 3 na silver, 3 na gold, código mudou e um controle sem defeito; `--listar` mostra o menu) gera sementes adulteradas, planta defeitos no código da silver e da gold, roda cargas reais num banco descartável, exige que a origem apontada seja a certa (sai com erro se não for) e gera o **PDF** `exports/relatorio_anomalias.pdf` com a explicação de anomalia real × alarme falso de cada cenário. `test_simulacao.py` confere o catálogo (3 cenários por camada, explicações completas) e a geração do PDF |
| `test_integridade.py` | **ninguém altera as camadas por fora sem ser barrado ou percebido**: UPDATE, DELETE, INSERT e TRUNCATE em bronze, silver e gold fora da carga são recusados; durante a carga passam; a trava é instalada uma vez (idempotente); trava desligada é detectada; uma pessoa alterada, uma conversa apagada, um número da gold alterado, uma linha da bronze trocada ou uma linha acrescentada mudam a impressão digital e a verificação aponta |
| `backend/tests/test_api_x_gold.py` + `conciliacao.py` | **a API devolve o que a gold tem**: cada endpoint de dados, em 6 países (Brasil, os 2 maiores, Portugal, Desconhecido e um com menos de 30 elegíveis), é comparado linha a linha com a gold (401 conferências); taxa e margem de Wilson são **recalculadas em Python** e comparadas com as da API; somas por semana, mês, versão e faixa têm de bater com `gold.pais` (dois caminhos, mesmo número); 14 conferências entre bronze, silver e gold; rotas sem login dão 401; **um erro plantado é detectado** (provado também alterando 1 número da gold: 5 testes quebraram) |
| `backend/tests/test_decomposicao.py` | mix + taxa + interação **soma exatamente** a variação (25 casos aleatórios); só o mix; só a taxa; nada mudou; nível que aparece em um mês só |

**Limite declarado:** os testes de tema e recusa fixam o comportamento atual das regras (regressão). Eles **não medem precisão**:
isso vem da amostra manual (`exports/amostra_validacao_*.csv`, `docs/VALIDACAO.md`).

## Prova de que os testes pegam o erro (mutação)
Alterei a definição de propósito e rodei a suíte; cada alteração foi **detectada** (depois revertida):
| Alteração feita | Testes que quebraram |
|---|---|
| gap de sessão 30 → 45 min | 2 (`parâmetros da definição`, `mais de 30 min abre nova sessão`) |
| janela de retorno 7 → 14 dias | 3 (parâmetros, limite de 7 dias, elegibilidade) |
| usuário com user-agent **bruto** (o erro do incidente) | 15 |
| início da conversa = último turno (o erro do incidente) | 4 |

## Camadas de proteção
1. **Estes testes** (código): a regra não muda sem quebrar um teste.
2. **O portão do ETL** (dados): a cada carga, 65 conferências comparam a base com os números validados (Power BI e DBeaver) e entre as camadas;
   se algo falhar, a carga é revertida e o dashboard continua no estado anterior.

## Como uma mudança chega à produção (desenho)
1. **Pull request:** o workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) roda os 108 testes, sobe a carga completa (o build do frontend confere os tipos) e exige o recálculo independente sem divergência. Sem verde, não faz merge (a proteção do branch `main` precisa exigir os dois jobs). **O workflow foi criado e a sintaxe conferida, mas ainda não foi executado no GitHub**: confirme o primeiro run.
2. **Migrações:** arquivos numerados em `db/migrations/`, aplicados em ordem pelo ETL e registrados em `public.schema_migrations`; migração já aplicada nunca é editada (cria-se uma nova).
3. **Ambientes:** `dev` (local, compose), `staging` (cópia na AWS com a mesma semente) e `prod`. A mudança de definição passa por `staging`, onde o portão do ETL compara os números novos com os antigos antes de promover.
4. **Deploy:** imagem nova (ECR) → ECS Fargate; o ETL roda primeiro (migra, carrega, confere); a API só sobe se o portão passar.
5. **Reversão:** a carga é uma transação (se falhar, nada é publicado) e a versão anterior da imagem continua disponível para voltar.