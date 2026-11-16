# ADR-004: arquitetura em camadas (bronze, silver, gold) e portão de qualidade

Status: aceita; **revisada em 12/11/2026** (a bronze passou de "arquivos Parquet" para "tabelas no Postgres", e a silver passou
a ler da bronze). Substitui o desenho de schema único `analytics` do ADR-003.

## Contexto
O PDF exige que o dashboard leia uma base analítica "desenhada e populada" por nós e (seção 4) que dê para investigar um número
errado e impedir que a definição de um indicador mude sem aviso. Um schema único mistura dado bruto, variáveis por usuário e
números de tela, e obriga a API a ter acesso a tudo.

## Opções
1. Schema único (`analytics`), como no primeiro esqueleto.
2. **Camadas bronze, silver e gold**, com permissões diferentes por camada.
3. Camadas com ferramenta pronta (dbt/Airflow): mais robusto em escala, mais peças para uma entrega local.

## Decisão
Opção 2, em Python + SQL, sem orquestrador. **Tudo no Postgres** e numa única transação:

| Camada | Conteúdo | Onde | Quem lê |
|---|---|---|---|
| Bronze | Cópia fiel do dado bruto numa **tabela única**, `bronze.wildchat` (todos os países; o Brasil com o texto e as mensagens em JSON, os demais só com metadados; `arquivo_origem` liga cada linha ao seu lote). Nada é limpo nem derivado. | Postgres `bronze` | só o ETL |
| Silver | Conversas e usuários limpos, deduplicados, com usuário/sessão/variáveis (BDR-001/003); **sem texto**. **Nasce da bronze**, em SQL. | Postgres `silver` | só o ETL |
| Gold | Agregados com IC, lista de países, efeitos estimados, catálogo de indicadores | Postgres `gold` | API (papel `api_ro`) |
| Ops | Execuções, linhagem dos lotes (arquivo, sha256, **tabela de destino**), resultados de qualidade | Postgres `ops` | ETL grava; API lê |

- **Por que a bronze ficou no banco (revisão):** guardar só o registro dos arquivos impedia consultar o dado bruto; não dava para
  rastrear em SQL como uma linha bruta virou uma linha da silver, que é o que a investigação de um número errado exige. Agora
  `SELECT * FROM bronze.wildchat` mostra o bruto, e dá para comparar bronze e silver na mesma consulta.
- **Silver lendo a bronze:** o DuckDB só lê o Parquet para carregar a bronze (`COPY`); a transformação é SQL do Postgres sobre as
  tabelas bronze. As regras de texto (tema, recusa) usam `etl_rx(texto, padrão)`, uma função da migração 004 (equivale a `~`).
- **Privacidade:** `bronze` contém o **texto** das conversas do Brasil. Só o ETL tem acesso a `bronze` e `silver`; o papel
  `api_ro` só tem `gold` e `ops` (testado: leitura de `bronze` é negada).
- **Idempotência e atomicidade:** as três camadas são esvaziadas e recarregadas numa única transação; a API nunca vê um estado
  pela metade (ela enxerga o estado anterior até o `COMMIT`).
- **Portão de qualidade:** `etl/camadas/*/validar.py (as validações de cada camada)` compara a carga com os números validados por conferência independente (Power BI e
  DBeaver; README, seção 6): 20 verificações, incluindo linhas da bronze = linhas dos arquivos, integridade do JSON e a
  distribuição de usuários por tema. Se algo divergir, `QA_ESTRITO=1` faz rollback e o ETL termina com erro (a API não sobe).
- **Definições em um lugar só:** `etl/comum/definicoes.py` (usuário, sessão, tema, recusa, parâmetros) e o SQL do gold.

## Consequências
- **Tabela única (revisão de 12/11):** os dois arquivos da semente continuam separados (tamanho, ADR-002), mas a bronze os junta em
  `bronze.wildchat`; as colunas que só existem em um deles (`conversation` e moderações) ficam `NULL` no outro.
  A silver deixou de unir duas tabelas: lê uma só. O início da conversa é `primeira_resposta_ts`, calculada igual para todos os países na semente.
- O banco cresceu de ~335 MB para ~830 MB (`bronze.wildchat` ocupa ~510 MB, incluindo os índices por hash e por país) e a carga leva
  ~80 s (bronze 14 s, silver 58 s). É o preço de ter o bruto consultável.
- A bronze é uma **cópia da semente**, não do bruto completo: os demais países vêm sem texto (ADR-002), e a coluna
  `primeira_resposta_ts` (início da conversa) foi extraída na geração da semente (`make_seed.py`), igual para todos.
- A reescrita da silver (DuckDB para SQL do Postgres) foi validada pelo próprio portão: todos os números, a distribuição por tema e
  os 16 efeitos da análise ficaram idênticos aos da versão anterior.
- Os valores esperados do portão estão no código: mudar uma definição de propósito exige atualizá-los junto, num commit revisável.
- A linhagem entre camadas (contagens, exclusões, nulos, antes e depois) está no ADR-005.
- Evolução natural na AWS: bronze em S3 (Parquet) e/ou tabelas no RDS, silver/gold em RDS, ETL agendado; dbt só se o volume e o
  time justificarem.
