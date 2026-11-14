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
| **Cada execução** | início, fim, status, versão do código, resultado de cada conferência | `ops.etl_execucao`, `ops.qa_resultado` | o painel do portão |

"Impressão digital" é uma soma de hashes das linhas: se **uma única** pessoa, conversa ou linha de resumo mudar, a impressão muda.

## 2. As seis proteções, da entrada à saída
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
6. **Testes automáticos e CI.** 128 testes (79 do ETL, 29 da API, 20 de integração API × gold) fixam cada regra de borda e reproduzem o incidente do PDF. O workflow `.github/workflows/ci.yml` roda os testes e a carga completa a cada push. **Foi criado e a sintaxe foi conferida, mas ainda não foi executado no GitHub**: confirme o primeiro run e, no GitHub, exija os dois jobs na proteção do branch `main`.

## 3. O que cada proteção pega (cenários)
| O que pode dar errado | Quem pega | Verificado? |
|---|---|---|
| A semente muda de formato | contrato | teste automático (coluna a menos, tipo trocado, coluna nova, arquivo ausente) e a semente real |
| A semente muda de conteúdo | sha256 diferente em `ops.bronze_lote`; deriva só com variação grande | teste automático |
| Alguém muda uma **regra ou parâmetro** (por exemplo, visita de 30 para 45 minutos) | números validados e deriva | **demonstrado**: com 45 minutos, o retorno do Brasil foi de 23,72% para 22,02%, as duas conferências falharam (a deriva apontou 234 medidas diferentes), a carga foi desfeita e os dados ficaram intactos |
| Bug na derivação (navegador, código da pessoa, início) | recálculo independente e testes | teste automático com erro plantado (voltou_7d, elegivel, voltou_24h) |
| Bug no agrupamento da gold | conferências de conservação (silver_gold) | 24 conferências por carga |
| A API devolve número diferente da gold (conta de taxa, filtro, ordem) | teste de integração API × gold | **demonstrado**: 1 número da gold alterado, 5 testes quebraram |
| Resultado diferente a cada execução | deriva com a mesma semente | duas cargas seguidas: 0 mudanças |
| Efeito estatístico mudou | impressão da `gold.efeito_fator` e medida `efeitos_brasil` | por deriva |
| Carga que falha no meio | transação única: rollback | demonstrado, dados intactos |
| Código quebrado chega ao GitHub | CI | **ainda não executado** |

## 4. Como investigar quando um número parecer errado
Conexão: DBeaver em `localhost:5433`, banco `retencao`, usuário `etl`.
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
- **Tela × API:** a API × gold é testada automaticamente (`backend/tests/test_api_x_gold.py`, 401 conferências em 6 países, não nos 202), mas **não há teste automático do que a tela desenha**: o painel só mostra o que a API devolve, e isso foi conferido à mão.
- **Números validados à mão:** precisam ser atualizados por uma pessoa, depois de conferir, quando uma definição muda de propósito.
- **Deriva por padrão só alerta:** `DERIVA_ESTRITA=1` a torna bloqueante (decisão de quem opera).
- **Impressões digitais** são somas de hashes de 64 bits: uma colisão é improvável, mas não impossível.
- **Tema e recusa** (regras de palavras): os testes fixam o comportamento, mas **não medem a precisão**; isso depende da amostra manual.
- **CI:** o workflow ainda não foi executado no GitHub e a proteção do branch precisa ser configurada lá.
- **Recálculo em todos os países:** por padrão só o Brasil (leve); `RECALCULO_PAISES=todos` leva mais tempo e memória.
