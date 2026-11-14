# Camada SILVER: o dado limpo, com as regras de negócio

**Em uma frase:** lê a bronze, limpa, define quem é a "pessoa", agrupa em visitas, marca quem **voltou** e quem é **elegível**, e deriva tema e recusa. **Não guarda texto de conversa nem endereço de internet.**

| | |
|---|---|
| **Entra** | `bronze.wildchat` |
| **Sai** | `silver.fato_conversa` (837.972 linhas), `silver.fato_usuario` (197.319 pessoas), `silver.dim_pais`, `silver.dim_tema` e o registro do que foi excluído (`auditoria.*`) |
| **Onde roda** | no Postgres (o Python só envia os comandos SQL) |

## Arquivos, na ordem em que rodam
| Arquivo | O que faz |
|---|---|
| [`limpar.py`](limpar.py) | esvazia as 4 tabelas da silver (num único `TRUNCATE`, porque se referenciam) |
| [`sql.py`](sql.py) | os comandos SQL, um por passo (veja abaixo) |
| [`construir.py`](construir.py) | executa os passos na ordem; devolve estatísticas (lidas, excluídas...) |
| [`auditoria.py`](auditoria.py) | grava no schema `auditoria` cada linha excluída (com o motivo), vazios antes e depois, exemplos antes/depois e o funil por país |
| [`validar.py`](validar.py) | 21 conferências (veja abaixo) |
| [`__init__.py`](__init__.py) | expõe `construir_silver`, `auditar_silver`, `validar_silver` |

As regras (30 minutos de visita, 7 dias, 30 dias de lavagem, palavras de tema e recusa) ficam em [`../../comum/definicoes.py`](../../comum/definicoes.py).

## Os passos do `sql.py`
| Passo | Tabela temporária | O que faz |
|---|---|---|
| 1 | `bruto` | achata a bronze: tira pedido e resposta do JSON, navegador, idioma do navegador; início = 1ª resposta do assistente |
| 2 | `conv0` | descarta linhas sem horário ou sem endereço e remove **cópias exatas** (17) |
| 3 | `dim_pais`, `dim_tema` | tabelas de apoio: país (fuso, ISO) e os 11 temas |
| 4 | `conv` | navegador/sistema sem versão, código da pessoa (`md5` do endereço + navegador), tamanhos, recusa e tema (só Brasil) |
| 5 | `usuarios` | visitas (30 min), voltou em 7 dias e em 24 h, dias até voltar, 1ª experiência, semana/hora/dia local, elegível |
| 6 | (definitivas) | grava `fato_conversa` e `fato_usuario`; as temporárias somem no fim da transação |

## Validações (`validar.py`)
- **bronze_silver (3):** bronze = silver + excluídas; toda conversa aponta para uma linha da bronze; país nulo = "Desconhecido" + excluídas.
- **silver_interna (8):** soma de `convs_total` = conversas; nenhuma pessoa em dois países; retorno, elegibilidade e 1ª vez **recalculados** a partir das conversas = os da silver; "voltou em 24 h" implica "voltou em 7 dias".
- **validados (10):** os números do Brasil continuam iguais aos que conferi à mão (11.621 conversas, 2.530 pessoas, 2.234 elegíveis, 23,72%, 911 recusas, os 11 temas…).

## Para conferir no DBeaver
```sql
SELECT count(*) FROM silver.fato_conversa;                       -- 837.972
SELECT count(*) FROM silver.fato_usuario;                        -- 197.319
SELECT * FROM auditoria.audite_usuario('1cb966329f48');          -- uma pessoa, passo a passo
```
E o recálculo por outro caminho: `analise/08_recalculo_independente.py` (0 divergências).

## Limites
"Pessoa" é uma aproximação (endereço + navegador); início = 1ª resposta do assistente; tema e recusa são regras de palavras, sem precisão medida ainda; fuso único por país.
