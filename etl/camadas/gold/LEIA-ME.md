# Camada GOLD: os resumos que a tela lê

**Em uma frase:** transforma as pessoas e conversas da silver em tabelas pequenas (por país, semana, mês, modelo, fator…), com **taxa e margem de erro** só quando há 30 ou mais pessoas, e estima os **efeitos** dos fatores. É a **única** camada que a API enxerga.

| | |
|---|---|
| **Entra** | `silver.fato_usuario`, `silver.fato_conversa`, `silver.dim_pais`, `silver.dim_tema` |
| **Sai** | 14 tabelas `gold.*` (pais, retorno por semana e por fator, curva, uso, concentração, efeitos, catálogo…) |
| **Onde roda** | resumos em SQL no Postgres; efeitos em Python (pandas + scikit-learn) |

## Arquivos, na ordem em que rodam
| Arquivo | O que faz |
|---|---|
| [`limpar.py`](limpar.py) | esvazia as tabelas da gold |
| [`sql.py`](sql.py) | os comandos SQL, um por tabela (a margem de erro é o intervalo de Wilson, `gold.wilson_lo/hi`) |
| [`construir.py`](construir.py) | executa os comandos na ordem e grava o catálogo de indicadores (`CATALOGO`, em `comum/definicoes.py`) |
| [`efeitos.py`](efeitos.py) | compara pessoas parecidas (AIPW, validação cruzada em 5 partes, E-value) e grava `gold.efeito_fator` (só Brasil, 16 efeitos) |
| [`auditoria.py`](auditoria.py) | completa o funil por país com os números da gold |
| [`validar.py`](validar.py) | 27 conferências (veja abaixo) |
| [`__init__.py`](__init__.py) | expõe `construir_gold`, `construir_efeitos`, `auditar_gold`, `validar_gold` |

## Validações (`validar.py`)
- **silver_gold (24):** cada soma da gold bate com a silver (pessoas e conversas por país, novos/elegíveis/voltaram por semana, uso diário, curva, concentração, uso por hora, modelo, recusa por versão…).
- **efeitos (3):** há efeitos para o Brasil, o intervalo contém a estimativa e nenhum grupo tem menos de 30 pessoas.

## Para conferir no DBeaver
```sql
SELECT sum(novos), sum(elegiveis), sum(voltaram_7d) FROM gold.agg_retorno_semana;   -- 197.319 · 174.629 · 37.540
SELECT contraste, efeito_bruto_pp, efeito_pp, ic_lo, ic_hi FROM gold.efeito_fator;
```

## Limites
O intervalo de Wilson supõe pessoas independentes (com "pessoa" aproximada, pode ser otimista). Os efeitos são **associação, não causa**; só 2 dos 16 resistem à correção para múltiplos testes (BDR-004).
