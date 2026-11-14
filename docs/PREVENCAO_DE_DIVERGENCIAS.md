# Prevenção e investigação de divergências

Objetivo (PDF 4.1): **nenhum número pode mudar sem ninguém perceber, e quando algo parecer errado, tem de ser fácil descobrir onde e quando.**
Este documento mostra o que o projeto registra em cada camada, como uma divergência é percebida, o que cada proteção pega, como investigar
e o que ainda **não** está coberto.

## 1. Visão em uma tabela
| Camada | O que é registrado a cada carga | Onde fica | Quem confere |
|---|---|---|---|
| **Semente** | formato dos arquivos (colunas e tipos) | falha antes de carregar | `bronze/contrato.py` |
| **Bronze** | arquivos lidos (nome, sha256, linhas, bytes); linhas por arquivo e por país; vazios por coluna; período; países | `ops.bronze_lote`, `auditoria.metrica` | `bronze/validar.py` (5) |
| **Silver** | cada linha excluída e o motivo; vazios antes e depois; exemplos antes/depois; funil por país; pessoas, elegíveis e retornos por país; temas; navegadores; **impressão digital** de todas as pessoas e conversas | `auditoria.registro_excluido`, `nulos`, `antes_depois`, `fluxo_pais`, `metrica` | `silver/validar.py` (8 + 3 + 10) e o **recálculo independente** (6) |
| **Gold** | linhas e **impressão digital** de cada uma das 14 tabelas; números de negócio do Brasil; efeitos | `auditoria.metrica` | `gold/validar.py` (27) |
| **Entre cargas** | o que mudou em relação à carga anterior | `auditoria.mudancas_entre_cargas` | **deriva** (1 por camada) |
| **Taxa por país** | funil por país (linhas, endereços distintos, vazios, conversas, pessoas, elegíveis, voltaram, gold) | `auditoria.metrica`, `auditoria.anomalia` | **anomalia** com origem provável (bronze, silver, gold, transformação) |
| **Depois da carga** | se alguém alterou bronze, silver ou gold por fora do ETL | `auditoria.verificacao` | **trava de escrita** (barra) e **verificação de integridade** (percebe) |
| **Cada execução** | início, fim, status, versão do código, resultado de cada conferência | `ops.etl_execucao`, `ops.qa_resultado` | o painel do portão |

"Impressão digital" é uma soma de hashes das linhas: se **uma única** pessoa, conversa ou linha de resumo mudar, a impressão muda.

## 2. As oito proteções, da entrada à saída
1. **Contrato da semente** (`camadas/bronze/contrato.py`). Antes de carregar, confere as colunas e os tipos dos dois Parquet. Coluna a menos, tipo trocado, coluna nova ou arquivo ausente: a carga **para** com uma mensagem clara, em vez de quebrar no meio ou carregar números errados.
2. **Conferências de conservação em cada camada.** "A soma de baixo é a de cima": bronze = silver + excluídas, soma das conversas por pessoa = conversas, cada resumo da gold = o que a silver tem. São 62 por carga (`camadas/*/validar.py`).
3. **Números validados à mão.** Os 10 números principais do Brasil (11.621 conversas, 2.530 pessoas, 2.234 elegíveis, 23,72%…) estão escritos no código; se uma regra mudar, eles quebram.
4. **Recálculo independente.** A silver é refeita em **Python (pandas) a partir da bronze**, com outro código, e comparada **pessoa por pessoa**. Há três níveis, cada um mais independente que o anterior:
   - `silver/validar.py`: recalcula as visitas a partir das conversas da própria silver (SQL);
   - `silver/recalculo_independente.py`: refaz também o código da pessoa, o navegador e o início, a partir da **bronze**, em Python (roda em toda carga; por padrão no Brasil, `RECALCULO_PAISES=todos` confere os 202 países);
   - `analise/08_recalculo_independente.py`: parte dos **arquivos da semente**, sem importar nada de `etl/`. Hoje: **0 divergências em 197.319 pessoas**.
5. **Deriva** (`comum/deriva.py`). Compara as medidas desta carga com as da carga anterior bem-sucedida:
   - **mesma semente** (mesmos sha256): os números têm de ser **iguais**; qualquer diferença quer dizer que uma regra, um parâmetro ou o código mudou, ou que o resultado não é reprodutível;
   - **semente nova**: só se aponta variação maior que 20%.
   Por padrão a deriva gera **alerta** (a carga é publicada e o status fica `alerta`); com `DERIVA_ESTRITA=1` ela desfaz a carga. Na carga seguinte a comparação parte da que gerou o alerta, então o alerta aparece uma vez por mudança.
6. **Trava de escrita e verificação de integridade** (migração `025`, `etl/verificacao.py`). As conferências acima só olham **no momento da carga**. E se alguém mexer na silver ou na gold **depois**?
   - **Barra:** `UPDATE`, `INSERT`, `DELETE` e `TRUNCATE` em qualquer tabela de bronze, silver e gold são **recusados** fora da carga (a carga avisa com `SET LOCAL etl.carga = 'on'`, que vale só até o fim da transação). O erro diz: "Camada protegida… só é permitido ao ETL". A trava é instalada em toda tabela das camadas, inclusive as criadas no futuro.
   - **Percebe:** a verificação mede de novo as 3 camadas (1.332 medidas, com a impressão digital de **todas** as linhas) e compara com o que a última carga gravou. Linha alterada, apagada ou **a mais**, em qualquer camada, muda a impressão digital. Confere também se a trava continua ligada.
   - **Quando roda:** no início de **toda carga**, antes de reconstruir (a carga cura a alteração, mas o alerta fica: status `alerta`), e quando você quiser: `docker compose --profile operacao run --rm verificar-integridade` (refaz também as conferências de conservação no banco vivo e sai com erro se algo divergir). Cada verificação fica em `auditoria.verificacao`.
   - **Acesso de consulta:** use o usuário `auditor` (somente leitura) no DBeaver, em vez de `etl`.
7. **Anomalia com diagnóstico de origem** (`comum/anomalia.py`, migração `026`). A deriva só pega mudança **com a mesma semente**; com dado novo, a taxa de um país pode mudar de 25% para 97% e ninguém saber de quem é a culpa. A cada carga, a taxa de retorno em 7 dias de cada país (com 30 ou mais elegíveis) é comparada com a da carga anterior; só vira anomalia se mudar **5 pontos percentuais ou mais** e for improvável de ser acaso (z ≥ 4). A taxa é olhada na silver **e** na gold (a tela mostra a da gold). Para cada anomalia, o funil é comparado camada por camada e aponta **onde a mudança começou**:
   | Origem | Como é decidida | O que fazer |
   |---|---|---|
   | **GOLD** | a gold não bate com a silver para o país | erro de agregação: `etl/camadas/gold/sql.py` |
   | **TRANSFORMAÇÃO** | arquivos de entrada idênticos (mesmo sha256) e resultado diferente | uma regra, parâmetro ou o código mudou: `auditoria.mudancas_entre_cargas` e o último commit |
   | **BRONZE** | o dado de entrada mudou de padrão: linhas do país (±30%), endereços distintos por linha (±20%), linhas sem endereço, sem horário ou sem navegador (±5 p.p.) | problema da fonte, **não do ETL**: confira os arquivos de origem antes de mexer no código |
   | **SILVER** | entrada normal, mas a limpeza descartou outra proporção (±5 p.p.), as pessoas por conversa mudaram (±20%) ou a proporção de elegíveis mudou (±10 p.p.) | `etl/camadas/silver/sql.py` e `auditoria.registro_excluido` |
   | **SEM CAUSA TÉCNICA** | todo o funil estável e a taxa mudou | pode ser mudança real de comportamento: confirme com a fonte |
   O diagnóstico mostra o funil inteiro (antes → agora) com `!!` nas etapas que mudaram, e fica em `auditoria.anomalia`. Há dois tipos: **TAXA** (a taxa saltou) e **ENTRADA** (a taxa quase não mexeu, mas o dado de entrada mudou de padrão: por exemplo, 60% das linhas sem endereço encolhem o país inteiro sem mudar a taxa; só olhar a taxa deixaria passar). É **alerta** (a carga é publicada com status `alerta`), não bloqueio. Para ver funcionando sem tocar no banco: `docker compose --profile operacao run --rm investigar-anomalias python -m comum.anomalia --simular Brazil bronze` (também `silver`, `gold` e `transformacao`).
8. **Testes automáticos e CI.** 160 testes (111 do ETL, 29 da API, 20 de integração API × gold) fixam cada regra de borda e reproduzem o incidente do PDF. O workflow `.github/workflows/ci.yml` roda os testes e a carga completa a cada push. **Foi criado e a sintaxe foi conferida, mas ainda não foi executado no GitHub**: confirme o primeiro run e, no GitHub, exija os dois jobs na proteção do branch `main`.

## 3. O que cada proteção pega (cenários)
| O que pode dar errado | Quem pega | Verificado? |
|---|---|---|
| A semente muda de formato | contrato | teste automático (coluna a menos, tipo trocado, coluna nova, arquivo ausente) e a semente real |
| A semente muda de conteúdo | sha256 diferente em `ops.bronze_lote`; deriva só com variação grande | teste automático |
| Alguém muda uma **regra ou parâmetro** (por exemplo, visita de 30 para 45 minutos) | números validados e deriva | **demonstrado**: com 45 minutos, o retorno do Brasil foi de 23,72% para 22,02%, as duas conferências falharam (a deriva apontou 234 medidas diferentes), a carga foi desfeita e os dados ficaram intactos |
| Bug na derivação (navegador, código da pessoa, início) | recálculo independente e testes | teste automático com erro plantado (voltou_7d, elegivel, voltou_24h) |
| Bug no agrupamento da gold | conferências de conservação (silver_gold) | 24 conferências por carga |
| A API devolve número diferente da gold (conta de taxa, filtro, ordem) | teste de integração API × gold | **demonstrado**: 1 número da gold alterado, 5 testes quebraram |
| Alguém edita a silver ou a gold por fora (DBeaver, script solto) | trava de escrita: o comando é recusado | **demonstrado** com o usuário `etl`: "Camada protegida: UPDATE em gold.pais só é permitido ao ETL" |
| Alguém desliga a trava (dono do banco) e altera 1 pessoa da silver | verificação de integridade: impressão digital e `voltaram_7d[Brazil]` (530 → 531) | **demonstrado**: a verificação manual acusou 7 conferências; a carga seguinte registrou o alerta (`alerta`), reconstruiu e a verificação voltou a 61 de 61 |
| Camada com linhas a mais ou a menos por fora | contagem e impressão digital (integridade) + bronze = silver + excluídas | teste automático (linha apagada, acrescentada, trocada) |
| A taxa de um país salta (25% → 97%) depois de uma carga | anomalia: z-test contra a carga anterior + funil por camada | teste automático das 5 origens e **simulação ponta a ponta** (`simular-cenarios`): semente adulterada e defeitos plantados no código de cada camada, num banco descartável; a origem certa foi apontada nos 4 cenários (veja a tabela abaixo) |
| Resultado diferente a cada execução | deriva com a mesma semente | duas cargas seguidas: 0 mudanças |
| Efeito estatístico mudou | impressão da `gold.efeito_fator` e medida `efeitos_brasil` | por deriva |
| Carga que falha no meio | transação única: rollback | demonstrado, dados intactos |
| Código quebrado chega ao GitHub | CI | **ainda não executado** |

### Simulação ponta a ponta do detector de anomalia
```bash
docker compose --profile operacao run --rm simular-cenarios      # cerca de 12 minutos; usa o banco descartável retencao_cenarios, nunca o real
```
Para cada cenário roda uma carga normal (referência) e uma com defeito (sem derrubar a carga, para ver também o portão). A semente oficial não é tocada; as sementes adulteradas ficam em `data/cenarios/` (fora do git). Resultado na última execução:
| Cenário | Defeito plantado | Taxa do Brasil | Origem apontada | Conferências do portão que também falharam |
|---|---|---|---|---|
| bronze | semente nova com 60% das conversas do Brasil sem endereço | 23,7% → 22,5% (quase igual!) | **BRONZE** (tipo ENTRADA) | 10 |
| silver | semente saudável + regra de elegibilidade errada na silver | 23,7% → 61,8% | **SILVER** | 8 |
| gold | semente saudável + agregação da gold triplica os que voltaram | 23,7% → 71,2% | **GOLD** | 5 |
| transformação | mesma semente oficial + regra de elegibilidade errada | 23,7% → 61,8% | **TRANSFORMAÇÃO** | 4 |

A primeira execução errou o cenário **bronze** (não apontou nada, porque a taxa quase não mudou). A simulação encontrou a falha do detector; ele ganhou o tipo ENTRADA e passou nos 4.

## 4. Como investigar quando um número parecer errado
Conexão: DBeaver em `localhost:5433`, banco `retencao`, usuário `auditor` (somente leitura, senha padrão `auditor` no ambiente local).
```sql
-- 1) O que mudou entre as duas últimas cargas? (vazio = nada)
SELECT * FROM auditoria.mudancas_entre_cargas ORDER BY camada, metrica, escopo;

-- 2) Quando um número mudou? (histórico de todas as cargas)
SELECT execucao_id, iniciado_em, status, valor, texto
FROM auditoria.historico_metrica
WHERE camada = 'silver' AND metrica = 'pessoas_elegiveis' AND escopo = 'Brazil' ORDER BY execucao_id;

-- 3) Que conferência falhou, em que carga?
SELECT execucao_id, transicao, verificacao, esperado, obtido
FROM ops.qa_resultado WHERE NOT passou ORDER BY id DESC;

-- 4) Algum arquivo de entrada mudou? (compare os sha256)
SELECT execucao_id, arquivo, left(sha256, 12), linhas FROM ops.bronze_lote ORDER BY execucao_id DESC, arquivo;

-- 5) O que foi excluído da bronze, e por quê?
SELECT motivo, count(*) FROM auditoria.registro_excluido GROUP BY 1;

-- 6) Uma pessoa, passo a passo
SELECT * FROM auditoria.audite_usuario('1cb966329f48');
```
```sql
-- 9) Que país teve a taxa mudada demais, e de onde veio? (origem: BRONZE, SILVER, GOLD, TRANSFORMACAO ou SEM_CAUSA)
SELECT execucao_id, pais, round(taxa_referencia * 100, 1) AS antes_pct, round(taxa_atual * 100, 1) AS agora_pct, origem, resumo, sinais
FROM auditoria.anomalia ORDER BY id DESC;
```
```sql
-- 7) Alguém alterou as camadas depois da carga? (histórico das verificações; divergencias > 0 = sim)
SELECT id, feita_em, origem, carga_verificada, conferencias, divergencias, detalhe FROM auditoria.verificacao ORDER BY id DESC;
-- 8) A trava de escrita está ligada em todas as tabelas? (protegida = false é alerta)
SELECT * FROM auditoria.protecao_camadas ORDER BY 1, 2;
```
E, por fora do banco, o recálculo a partir dos arquivos (sai com erro se houver qualquer divergência):
```bash
docker compose run --rm --no-deps -v "${PWD}\analise\08_recalculo_independente.py:/tmp/r.py:ro" etl python /tmp/r.py
```

## 5. Como uma mudança chega à produção
1. **Mudança no código ou na regra** → pull request → CI roda os testes e a carga completa.
2. **Migrações:** arquivos numerados em `db/migrations/`, aplicados uma vez e **nunca editados** depois de aplicados (cria-se uma nova).
3. **Mudança intencional de uma definição:** a carga mostra a deriva (alerta) e os números validados quebram; quem mudou atualiza os números validados **depois de conferir à mão** (`docs/VALIDACAO.md`) e documenta a decisão (BDR).
4. **Staging com a mesma semente:** a deriva compara os números novos com os antigos antes de promover.
5. **Deploy:** o ETL roda primeiro (migra, carrega, confere); a API só sobe se o portão passar. **Reversão:** a carga é uma transação, então uma carga que falha não publica nada, e a imagem anterior continua disponível.

## 6. Limites declarados (o que ainda não está coberto)
- **Parâmetro errado em ambos os lados:** o recálculo independente usa os mesmos parâmetros de `comum/definicoes.py` (30 min, 7 dias, 30 dias). Ele confirma que o **código** segue a regra, não que a **regra** é boa. Quem pega um parâmetro alterado são os números validados e a deriva.
- **Quem é dono do banco pode desligar a trava:** ela barra o acidente. Quem desliga de propósito é pego pela verificação, mas só quando ela roda (a cada carga ou sob demanda); nada a executa sozinha entre cargas, nem avisa por e-mail. Alterar `auditoria.metrica` junto com a tabela esconderia a mudança: em produção, só o ETL deve ter permissão de escrita (papel `auditor` para consulta; na AWS, IAM e papéis separados).
- **Anomalia só avalia a taxa de retorno em 7 dias**, por país, contra a carga **anterior** (não contra uma média histórica nem contra a sazonalidade) e só onde há 30 ou mais elegíveis. Os limites (5 p.p., z ≥ 4, 30%, 20%...) são escolhas, não verdades: ajuste-os em `comum/anomalia.py` com a experiência de operação. A origem é uma **pista**, não prova: aponta a primeira camada que mudou, e o diagnóstico depende de os sinais escolhidos terem mudado (um defeito em outra coluna da bronze pode cair em "SILVER" ou "SEM CAUSA"). É alerta, não bloqueia a publicação.
- **Migração que altera dado de camada** precisa de `SET LOCAL etl.carga = 'on'`, senão a trava a recusa depois da primeira carga.
- **Tela × API:** a API × gold é testada automaticamente (`backend/tests/test_api_x_gold.py`, 401 conferências em 6 países, não nos 202), mas **não há teste automático do que a tela desenha**: o painel só mostra o que a API devolve, e isso foi conferido à mão.
- **Números validados à mão:** precisam ser atualizados por uma pessoa, depois de conferir, quando uma definição muda de propósito.
- **Deriva por padrão só alerta:** `DERIVA_ESTRITA=1` a torna bloqueante (decisão de quem opera).
- **Impressões digitais** são somas de hashes de 64 bits: uma colisão é improvável, mas não impossível.
- **Tema e recusa** (regras de palavras): os testes fixam o comportamento, mas **não medem a precisão**; isso depende da amostra manual.
- **CI:** o workflow ainda não foi executado no GitHub e a proteção do branch precisa ser configurada lá.
- **Recálculo em todos os países:** por padrão só o Brasil (leve); `RECALCULO_PAISES=todos` leva mais tempo e memória.
