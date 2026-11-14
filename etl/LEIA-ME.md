# Pasta `etl/`: como o dado vira número

O ETL roda **uma vez** a cada `docker compose up` (container `etl`) e termina. Cada camada tem a sua pasta, com o mesmo desenho:
**limpar → construir → (auditar) → validar.** O arquivo [`main.py`](main.py) é só a "receita" que chama as camadas em ordem.

```
etl/
├── main.py                  a receita: preparar → BRONZE → SILVER → GOLD → publicar
├── camadas/
│   ├── bronze/              o dado como veio            (LEIA-ME.md dentro)
│   ├── silver/              o dado limpo, com as regras (LEIA-ME.md dentro)
│   └── gold/                os resumos que a tela lê     (LEIA-ME.md dentro)
├── comum/                   o que todas as camadas usam: banco, contas, regras de negócio, portão de qualidade
├── semente/                 como os arquivos de entrada foram gerados (feito uma vez, à mão; não roda no Docker)
└── tests/                   111 testes automáticos aqui (mais 49 na API; veja docs/TESTES.md)
```

## A receita (o que `main.py` faz, em ordem)
| # | Passo | Função chamada | O que acontece |
|---|---|---|---|
| 0 | Preparar | `banco.migrar`, `acesso.garantir_conta_avaliacao`, `banco.abrir_execucao` | cria as tabelas (só as que faltam), as contas de acesso e abre o registro da carga |
| 0b | Integridade | `verificacao.estado_publicado` | **antes de reconstruir**, confere se o que está publicado é idêntico ao que a carga anterior deixou (ninguém alterou fora do ETL); só alerta. Depois liga `etl.carga = 'on'`, que libera a escrita nas camadas (trava da migração 025). Sob demanda: `docker compose --profile operacao run --rm verificar-integridade` |
| 1 | Bronze | `bronze.construir_bronze` (confere o contrato da semente antes) → `bronze.validar_bronze` → medir | registra os arquivos, esvazia a tabela e carrega os Parquet; confere se bate com os arquivos |
| 2 | Silver | `silver.construir_silver` → `silver.auditar_silver` → `silver.validar_silver` → medir | limpa, define pessoa/visitas/retorno/elegibilidade, registra o que foi excluído; confere |
| 3 | Gold | `gold.construir_gold` → `gold.construir_efeitos` → `gold.auditar_gold` → `gold.validar_gold` → medir | monta os resumos e estima os efeitos; confere que as somas batem com a silver |
| 3b | Anomalias | `anomalia.verificar` | compara a taxa de retorno de cada país com a da carga anterior; se saltar demais, aponta a origem (bronze, silver, gold ou transformação) no log e em `auditoria.anomalia`; só alerta. Sob demanda: `docker compose --profile operacao run --rm investigar-anomalias` |
| 4 | Publicar | `COMMIT` | só se **todas** as validações passaram; senão `ROLLBACK` e nada é publicado |

As três camadas são reconstruídas **por inteiro, numa única transação**. Se uma validação falha (modo estrito), a carga é desfeita e o painel continua com os dados anteriores.

## Onde fica cada coisa
| Quero ver… | Abra |
|---|---|
| a ordem da carga | [`main.py`](main.py) |
| como o arquivo Parquet vira a tabela bronze | [`camadas/bronze/carregar.py`](camadas/bronze/carregar.py) |
| as regras de "pessoa", visita, retorno e elegibilidade | [`camadas/silver/sql.py`](camadas/silver/sql.py) (os comandos) e [`comum/definicoes.py`](comum/definicoes.py) (os números e as palavras) |
| os resumos da tela | [`camadas/gold/sql.py`](camadas/gold/sql.py) |
| o cálculo dos efeitos | [`camadas/gold/efeitos.py`](camadas/gold/efeitos.py) |
| o histórico e a deriva | `comum/diagnostico.py`, `comum/deriva.py` e `camadas/<camada>/diagnosticar.py` |
| as conferências | `camadas/<camada>/validar.py` (65 no total, contando 6 do recálculo independente e a deriva de cada camada) |
| como conectar e migrar o banco | [`comum/banco.py`](comum/banco.py) |
| como a semente foi gerada | [`semente/`](semente/) |

**"Medir"** grava as medidas da camada em `auditoria.metrica` (histórico de todas as cargas) e compara com a carga anterior: se a semente é a mesma e os números mudaram, é **deriva** (alerta). Como investigar e o que cada proteção pega: [`docs/PREVENCAO_DE_DIVERGENCIAS.md`](../docs/PREVENCAO_DE_DIVERGENCIAS.md).

Documento com a lógica, o porquê de cada escolha e a conciliação de ponta a ponta: [`docs/CAMADAS_BRONZE_A_GOLD.md`](../docs/CAMADAS_BRONZE_A_GOLD.md).
