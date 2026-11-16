# ADR-004: camadas bronze, silver e gold e conferências por camada

Status: aceita (revisada em 12/11/2026: a bronze passou de arquivos para tabela no Postgres).

## Contexto
O PDF pede uma base analítica criada por nós e que seja possível investigar um número errado e impedir que uma definição mude sem aviso. Um schema único mistura dado bruto, variáveis por pessoa e números de tela, e obriga a API a acessar tudo.

## Opções
1. **Schema único.** Simples, mas sem separação de permissão nem de rastreio.
2. **Bronze, silver e gold com permissões por camada.** Em Python e SQL, sem orquestrador.
3. **dbt ou Airflow.** Mais robusto em escala, mais peças para uma entrega local.

## Decisão
Opção 2, tudo no Postgres e numa única transação:

| Camada | Conteúdo | Quem lê |
|---|---|---|
| Bronze | Cópia fiel da semente em `bronze.wildchat` (todos os países; só o Brasil tem texto). Nada é limpo nem derivado. | só o ETL |
| Silver | Conversas e pessoas limpas, sem duplicatas, com pessoa, sessão e variáveis (BDR-001 e BDR-003); sem texto. Nasce da bronze, em SQL. | só o ETL |
| Gold | Agregados com intervalo, países, efeitos e catálogo de indicadores. | API (papel `api_ro`) |
| Ops | Execuções, lotes (arquivo, sha256, tabela de destino) e resultado das conferências. | ETL grava, API lê |

- **Bronze no banco:** guardar só o registro dos arquivos impedia seguir uma linha bruta até a silver em SQL. Agora `SELECT * FROM bronze.wildchat` mostra o bruto.
- **Privacidade:** a bronze tem o texto do Brasil, então só o ETL acessa bronze e silver. O papel `api_ro` só vê gold e ops (testado: ler a bronze é negado).
- **Atomicidade:** as três camadas são esvaziadas e recarregadas numa transação; a API vê o estado anterior até o `COMMIT`.
- **Conferências:** 66 por carga (ADR-005), por exemplo "linhas da bronze = conversas da silver + excluídas" e 10 números do Brasil validados. Falha de conservação ou desses números cancela a carga (rollback, status `falhou`). Anomalia retém a carga até aprovação (ADR-006).
- **Definições em um lugar só:** `etl/comum/definicoes.py` e o SQL da gold. Os valores esperados das conferências ficam no código; mudar uma definição de propósito exige atualizá-los no mesmo commit.

## Consequências
- Os dois arquivos da semente continuam separados (tamanho, ADR-002), mas a bronze os junta. As colunas que só existem em um ficam `NULL` no outro. O início da conversa é `primeira_resposta_ts`, calculado igual para todos os países ao gerar a semente.
- O banco tem cerca de 870 MB (a bronze ocupa ~510 MB, com índices) e a carga leva cerca de 3 minutos. É o preço de ter o bruto consultável.
- A reescrita da silver de DuckDB para SQL do Postgres deu números idênticos, inclusive os 16 efeitos.
- Na AWS: bronze em S3 ou RDS, silver e gold em RDS, ETL agendado; dbt só se o volume e o time justificarem.
