# Indicadores: definição, fórmula, denominador e consulta de referência

Gerado a partir de `etl/pipeline/definicoes.py` (`CATALOGO`), a fonte única que também alimenta o botão "i" do dashboard (que mostra só a fórmula).
A consulta de referência usa o parâmetro `:pais` e as tabelas do banco analítico (ver `docs/arquitetura.md`).

## Retorno em 7 dias (`retorno_7d`)

- **Pergunta:** De cada 100 pessoas que experimentaram o assistente, quantas voltam em até 7 dias?
- **Fórmula:** usuários elegíveis com nova sessão iniciada em até 7 dias após a primeira ÷ usuários elegíveis
- **Denominador:** Usuários elegíveis: primeira vez há pelo menos 7 dias do fim dos dados e depois dos 30 primeiros dias
- **Unidade:** usuário
- **Período de referência:** Semana de chegada (segunda a domingo) no fuso do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_semana (origem: silver.fato_usuario)

```sql
SELECT count(*) FILTER (WHERE voltou_7d)::numeric / count(*) FROM silver.fato_usuario WHERE elegivel AND pais = :pais
```

## Usuários novos (`usuarios_novos`)

- **Pergunta:** Quantas pessoas usaram o assistente pela primeira vez em cada semana?
- **Fórmula:** contagem de usuários distintos pela semana da primeira conversa
- **Denominador:** não se aplica (contagem)
- **Unidade:** usuário
- **Período de referência:** Semana de chegada, no fuso do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_semana.novos

```sql
SELECT semana, count(*) FROM silver.fato_usuario WHERE pais = :pais GROUP BY semana
```

## Usuários elegíveis (`usuarios_elegiveis`)

- **Pergunta:** Quantos usuários têm janela completa para medir o retorno?
- **Fórmula:** usuários novos cuja primeira vez está a mais de 30 dias do início e a mais de 7 dias do fim dos dados
- **Denominador:** Usuários novos
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_semana.elegiveis

```sql
SELECT count(*) FROM silver.fato_usuario WHERE elegivel AND pais = :pais
```

## Conversas (`conversas`)

- **Pergunta:** Quantas conversas o assistente teve no período, e quantas por usuário?
- **Fórmula:** contagem de conversas, depois de excluir as cópias exatas
- **Denominador:** não se aplica (contagem); por usuário = conversas ÷ usuários
- **Unidade:** conversa
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais.conversas (origem: silver.fato_conversa)

```sql
SELECT count(*) FROM silver.fato_conversa WHERE pais = :pais
```

## Turnos médios (`turnos_medios`)

- **Pergunta:** Quantos turnos (trocas de mensagem) tem, em média, a 1ª conversa de cada usuário?
- **Fórmula:** média do número de turnos da 1ª conversa de cada usuário; a mediana é o valor do meio
- **Denominador:** Usuários do país
- **Unidade:** turno
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais (origem: silver.fato_usuario)

```sql
SELECT avg(turnos), percentile_cont(0.5) WITHIN GROUP (ORDER BY turnos) FROM silver.fato_usuario WHERE pais = :pais
```

## Uso de GPT-4 (`uso_gpt4`)

- **Pergunta:** Que parte das 1ªs conversas usou um modelo GPT-4?
- **Fórmula:** usuários cuja 1ª conversa usou um modelo GPT-4 ÷ usuários
- **Denominador:** Usuários do país
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.pais.pct_gpt4 (origem: silver.fato_usuario)

```sql
SELECT avg((modelo LIKE 'gpt-4%')::int) FROM silver.fato_usuario WHERE pais = :pais
```

## Recusa na primeira resposta (`recusa_primeira_conversa`)

- **Pergunta:** Em quantos usuários a primeira resposta do assistente abre com recusa ou desculpa?
- **Fórmula:** usuários elegíveis cuja primeira resposta casa o padrão de recusa ÷ usuários elegíveis
- **Denominador:** Usuários elegíveis de países com texto (hoje só o Brasil)
- **Unidade:** usuário
- **Período de referência:** Todo o período dos dados do país
- **Amostra mínima:** 30 (abaixo disso a tela esconde a taxa e o intervalo)
- **Fonte no banco:** gold.agg_retorno_fator (fator = recusa)

```sql
SELECT count(*) FILTER (WHERE recusa)::numeric / count(*) FROM silver.fato_usuario WHERE elegivel AND recusa IS NOT NULL AND pais = :pais
```
