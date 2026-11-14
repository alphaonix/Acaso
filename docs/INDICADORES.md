# Indicadores: definição, fórmula, denominador e consulta de referência

Gerado a partir de `etl/comum/definicoes.py` (`CATALOGO`), a fonte única que também alimenta o botão "i" do dashboard (que mostra só a fórmula).
A consulta de referência usa o parâmetro `:pais` e as tabelas do banco analítico (ver `docs/arquitetura.md`).

## Retorno em 7 dias (`retorno_7d`)

- **Pergunta:** De cada 100 pessoas que experimentaram o assistente, quantas voltam em até 7 dias?
- **Fórmula:** pessoas elegíveis com nova sessão iniciada em até 7 dias após a primeira ÷ pessoas elegíveis
- **Denominador:** pessoas elegíveis: primeira vez há pelo menos 7 dias do fim dos dados e depois dos 30 primeiros dias
- **Unidade:** usuário
- **Período de referência:** Semana de chegada (segunda a domingo) no fuso do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_semana (origem: silver.fato_usuario)

```sql
SELECT count(*) FILTER (WHERE voltou_7d)::numeric / count(*) FROM silver.fato_usuario WHERE elegivel AND pais = :pais
```

## Pessoas novas (`usuarios_novos`)

- **Pergunta:** Quantas pessoas usaram o assistente pela primeira vez em cada semana?
- **Fórmula:** contagem de pessoas distintos pela semana da primeira conversa
- **Denominador:** não se aplica (contagem)
- **Unidade:** usuário
- **Período de referência:** Semana de chegada, no fuso do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_semana.novos

```sql
SELECT semana, count(*) FROM silver.fato_usuario WHERE pais = :pais GROUP BY semana
```

## Pessoas elegíveis (`usuarios_elegiveis`)

- **Pergunta:** Quantos pessoas têm janela completa para medir o retorno?
- **Fórmula:** pessoas novos cuja primeira vez está a mais de 30 dias do início e a mais de 7 dias do fim dos dados
- **Denominador:** Pessoas novas
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_semana.elegiveis

```sql
SELECT count(*) FROM silver.fato_usuario WHERE elegivel AND pais = :pais
```

## Conversas (`conversas`)

- **Pergunta:** Quantas conversas o assistente teve no período, e quantas por pessoa?
- **Fórmula:** contagem de conversas, depois de excluir as cópias exatas
- **Denominador:** não se aplica (contagem); por pessoa = conversas ÷ Pessoas
- **Unidade:** conversa
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais.conversas (origem: silver.fato_conversa)

```sql
SELECT count(*) FROM silver.fato_conversa WHERE pais = :pais
```

## Turnos médios (`turnos_medios`)

- **Pergunta:** Quantos turnos (trocas de mensagem) tem, em média, a 1ª conversa de cada pessoa?
- **Fórmula:** média do número de turnos da 1ª conversa de cada pessoa; a mediana é o valor do meio
- **Denominador:** Pessoas do país
- **Unidade:** turno
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais (origem: silver.fato_usuario)

```sql
SELECT avg(turnos), percentile_cont(0.5) WITHIN GROUP (ORDER BY turnos) FROM silver.fato_usuario WHERE pais = :pais
```

## Uso de GPT-4 (`uso_gpt4`)

- **Pergunta:** Que parte das 1ªs conversas usou um modelo GPT-4?
- **Fórmula:** pessoas cuja 1ª conversa usou um modelo GPT-4 ÷ pessoas
- **Denominador:** Pessoas do país
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais.pct_gpt4 (origem: silver.fato_usuario)

```sql
SELECT avg((modelo LIKE 'gpt-4%')::int) FROM silver.fato_usuario WHERE pais = :pais
```

## Recusa na primeira resposta (`recusa_primeira_conversa`)

- **Pergunta:** Em quantos pessoas a primeira resposta do assistente abre com recusa ou desculpa?
- **Fórmula:** pessoas elegíveis cuja primeira resposta casa o padrão de recusa ÷ pessoas elegíveis
- **Denominador:** Pessoas elegíveis de países com texto (hoje só o Brasil)
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_fator (fator = recusa)

```sql
SELECT count(*) FILTER (WHERE recusa)::numeric / count(*) FROM silver.fato_usuario WHERE elegivel AND recusa IS NOT NULL AND pais = :pais
```

## Voltou em 24 horas (`voltou_24h`)

- **Pergunta:** De cada 100 pessoas, quantas voltam em até 24 horas depois do início da 1ª conversa?
- **Fórmula:** pessoas com nova sessão iniciada em até 24 horas após o início da 1ª conversa ÷ pessoas com 30 dias completos
- **Denominador:** Pessoas com janela completa de 30 dias (1ª vez há mais de 30 dias do início e do fim dos dados)
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_curva_retorno (dias = 1)

```sql
SELECT count(*) FILTER (WHERE voltou_24h)::numeric / count(*) FROM silver.fato_usuario WHERE janela_30d AND pais = :pais
```

## Voltou em 24 horas (base do retorno em 7 dias) (`voltou_24h_elegivel`)

- **Pergunta:** De cada 100 pessoas elegíveis, quantas voltam em até 24 horas depois do início da 1ª conversa?
- **Fórmula:** pessoas elegíveis com nova sessão iniciada em até 24 horas após o início da 1ª conversa ÷ pessoas elegíveis
- **Denominador:** Pessoas elegíveis (1ª vez há mais de 30 dias do início e 7 dias antes do fim dos dados): a mesma base do retorno em 7 dias
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais (voltaram_24h, usuarios_elegiveis)

```sql
SELECT count(*) FILTER (WHERE voltou_24h)::numeric / count(*) FROM silver.fato_usuario WHERE elegivel AND pais = :pais
```

## Voltou em 30 dias (`voltou_30d`)

- **Pergunta:** De cada 100 pessoas, quantas voltam em até 30 dias depois do início da 1ª conversa?
- **Fórmula:** pessoas com nova sessão iniciada em até 30 dias após o início da 1ª conversa ÷ pessoas com 30 dias completos
- **Denominador:** Pessoas com janela completa de 30 dias (1ª vez há mais de 30 dias do início e do fim dos dados)
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_curva_retorno (dias = 30)

```sql
SELECT count(*) FILTER (WHERE dias_ate_voltar <= 30)::numeric / count(*) FROM silver.fato_usuario WHERE janela_30d AND pais = :pais
```

## Concentração do uso (10 mais ativas) (`concentracao_top10`)

- **Pergunta:** Que parte das conversas vem das 10 pessoas mais ativas?
- **Fórmula:** conversas das 10 pessoas com mais conversas ÷ conversas do país; alerta de uso concentrado a partir de 25%
- **Denominador:** Conversas do país (depois de excluir as cópias exatas)
- **Unidade:** conversa
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais.top10_pct (origem: silver.fato_conversa)

```sql
WITH u AS (SELECT usuario_id, count(*) AS n FROM silver.fato_conversa WHERE pais = :pais GROUP BY 1) SELECT (SELECT sum(n) FROM (SELECT n FROM u ORDER BY n DESC, usuario_id LIMIT 10) x)::numeric / (SELECT sum(n) FROM u)
```

## Recusa por versão do modelo (`recusa_por_versao`)

- **Pergunta:** Em que parte das conversas a primeira resposta abre com recusa, em cada versão do modelo?
- **Fórmula:** conversas da versão cuja primeira resposta casa o padrão de recusa ÷ conversas da versão
- **Denominador:** Conversas com texto, da versão do modelo
- **Unidade:** conversa
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_recusa_modelo (origem: silver.fato_conversa)

```sql
SELECT modelo, count(*) FILTER (WHERE recusa)::numeric / count(*) FROM silver.fato_conversa WHERE recusa IS NOT NULL AND pais = :pais GROUP BY modelo
```
