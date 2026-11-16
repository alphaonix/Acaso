# Conferir cada número do dashboard em SQL

Cada número que aparece nas telas tem aqui uma consulta que **refaz a conta a partir da silver** (pessoa por pessoa, conversa por conversa) e a **compara com o que a gold guarda**, que é o que a tela mostra.
Quando a consulta tem a coluna `bate_com_gold`, ela deve vir **`t`** (verdadeiro). Se vier `f`, o número da tela não corresponde à silver.

## Como usar
1. No DBeaver, conecte em `localhost:5433`, banco `retencao`, usuário `auditor`, senha `auditor` (somente leitura).
2. Cole a consulta e execute (Ctrl+Enter).
3. Compare com a linha "Deve dar" logo abaixo e com o que a tela mostra.

**Para outro país:** use *Localizar e substituir* (Ctrl+F no editor do DBeaver) e troque `'Brazil'` por `'Germany'` (ou `'Portugal'`, `'United States'`) **em todos os lugares** da consulta. O nome é o da base, em inglês, mesmo com a tela em português.
Os valores abaixo são do Brasil; a Alemanha aparece ao lado quando ajuda a entender (a tela dela mostra 18,9% de retorno).

## Três palavras que aparecem em tudo
- **Pessoa** = uma linha de `silver.fato_usuario`: IP (anonimizado) + família do navegador e do sistema, sem versão. Ver o [README](../README.md#5-definições-e-premissas).
- **Elegível** = pessoa cuja primeira vez tem a janela completa: 30 dias depois do início dos dados e 7 dias antes do fim. É o denominador do retorno em 7 dias.
- **Gold** = os resumos prontos que a API lê. A tela nunca lê a silver.

## Onde está cada número

| Tela | Número | Seção |
|---|---|---|
| Visão geral | "De onde vêm estes dados" (conversas, pessoas, período) | 1.1 |
| | Cartões: pessoas novas, retorno em 7 dias (e o intervalo), conversas, recusa, voltou em 24 h, concentração | 1.2 a 1.7 |
| | "A história em 8 passos" | 1.8 |
| | Retorno por mês e a frase de tendência | 1.9 |
| | Comparação de modelos (por família e por versão) | 1.10 |
| | Curva de retorno | 1.11 |
| | Mapa de calor dia × hora | 1.12 |
| | GPT-4 por mês | 1.13 |
| | Concentração do uso (faixas e retorno sem as 10 mais ativas) | 1.14 |
| | Comparação entre países e média geral | 1.15 |
| Coortes semanais | Pessoas novas e retorno por semana (incluindo a semana do PDF) | 2.1 |
| | Decomposição: chegou gente diferente × a mesma gente voltou diferente | 2.2 |
| O que faz voltar | Efeitos: grupos e efeito bruto (16 linhas) | 3.1 |
| | Efeito ajustado, intervalo, etiqueta "resiste à correção" | 3.2 e 3.3 |
| | Os 4 achados (impacto no retorno, saudação e recusa por modelo) | 3.4 |
| | Turnos, dispositivo, sistema, navegador, idioma × navegador | 3.5 |
| Ajuda | Problemas de qualidade dos dados (11) | 4.1 |
| Todas | Da bronze para a silver: nada sumiu | 4.2 |

---

# 1. Visão geral

## 1.1 De onde vêm estes dados
**Na tela:** "11.621 conversas de 2.530 pessoas, de 09/04/2023 a 29/04/2024" e o total de todos os países (837.972).
```sql
-- Conta conversas e pessoas do país na silver, acha a primeira e a última data (em UTC) e compara com a gold.
SELECT (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil') AS conversas,
       (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil') AS pessoas,
       (SELECT (min(inicio_utc) AT TIME ZONE 'UTC')::date FROM silver.fato_conversa WHERE pais = 'Brazil') AS primeira_data,
       (SELECT (max(inicio_utc) AT TIME ZONE 'UTC')::date FROM silver.fato_conversa WHERE pais = 'Brazil') AS ultima_data,
       (SELECT count(*) FROM silver.fato_conversa) AS conversas_todos_os_paises,
       (SELECT (g.conversas = (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')
                AND g.usuarios = (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil')
                AND g.primeira_data = (SELECT (min(inicio_utc) AT TIME ZONE 'UTC')::date FROM silver.fato_conversa WHERE pais = 'Brazil'))
        FROM gold.pais g WHERE g.pais = 'Brazil') AS bate_com_gold;
```
**Passo a passo:** `silver.fato_conversa` tem uma linha por conversa e `silver.fato_usuario` uma por pessoa, então `count(*)` dá os totais. `inicio_utc` é o início da conversa (a 1ª resposta do assistente); `min` e `max` dão o período. `AT TIME ZONE 'UTC'` garante a mesma data que a tela, mesmo que o seu DBeaver use outro fuso.
**Deve dar:** 11.621 · 2.530 · 2023-04-09 · 2024-04-29 · 837.972 · `t`. (Alemanha: 28.975 conversas e 4.544 pessoas.)
**Por que 09/04 e não 08/04:** a data é em UTC; no horário de São Paulo o primeiro dia é 08/04 (ver README, seção 5).

## 1.2 Pessoas novas
**Na tela:** cartão "Pessoas novas" = 2.530.
```sql
-- Pessoas na silver, na soma das semanas da gold e no total do país da gold: os três têm de ser iguais.
SELECT (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil')                  AS pessoas_silver,
       (SELECT sum(novos) FROM gold.agg_retorno_semana WHERE pais = 'Brazil')            AS pessoas_gold_semanas,
       (SELECT usuarios FROM gold.pais WHERE pais = 'Brazil')                            AS pessoas_gold_pais;
```
**Passo a passo:** conta as pessoas (uma linha cada) e compara com duas somas da gold: a das semanas (usada nos gráficos) e a do país (usada no cartão).
**Deve dar:** 2.530 nos três (Alemanha: 4.544).

## 1.3 Retorno em 7 dias (o 23,7%)
**Na tela:** "23,7%", "530 de 2.234" e o intervalo "22,0% a 25,5%". É o número principal do projeto.
```sql
-- (a) A taxa: pessoas elegíveis, quantas voltaram em até 7 dias, e a divisão. Compara com a gold.
WITH s AS (SELECT count(*) FILTER (WHERE elegivel)                    AS n,
                  count(*) FILTER (WHERE elegivel AND voltou_7d)      AS v
           FROM silver.fato_usuario WHERE pais = 'Brazil'),
     g AS (SELECT sum(elegiveis) AS n, sum(voltaram_7d) AS v
           FROM gold.agg_retorno_semana WHERE pais = 'Brazil')
SELECT s.n AS elegiveis, s.v AS voltaram, round(s.v::numeric / s.n, 4) AS retorno,
       (s.n = g.n AND s.v = g.v) AS bate_com_gold
FROM s, g;
```
**Passo a passo:** `elegivel` marca quem tem a janela completa. `voltou_7d` marca quem iniciou uma **nova sessão** em até 7 dias depois da primeira vez (conversas com menos de 30 minutos entre si são a mesma sessão). A taxa é voltaram ÷ elegíveis. A parte `g` soma as semanas da gold.
**Deve dar:** 2.234 · 530 · 0,2372 · `t` (Alemanha: 3.835 · 723 · 0,1885 · `t`).

```sql
-- (b) O intervalo de confiança de 95% (Wilson), calculado na mão.
WITH b AS (SELECT count(*)::numeric AS n, count(*) FILTER (WHERE voltou_7d)::numeric AS v
           FROM silver.fato_usuario WHERE elegivel AND pais = 'Brazil'),
     p AS (SELECT n, v / n AS p, 1.96 AS z FROM b)
SELECT round((p + z^2 / (2*n) - z * sqrt(p*(1-p)/n + z^2 / (4*n^2))) / (1 + z^2/n), 4) AS ic_inferior,
       round((p + z^2 / (2*n) + z * sqrt(p*(1-p)/n + z^2 / (4*n^2))) / (1 + z^2/n), 4) AS ic_superior
FROM p;
```
**Passo a passo:** aplica a fórmula do intervalo de Wilson com `z = 1,96`. Ele diz "o valor verdadeiro provavelmente está entre estes dois números". É mais confiável que a margem simples quando a amostra é pequena. Não depende de nenhuma função do banco.
**Deve dar:** 0,2201 e 0,2553 (22,0% a 25,5%). Alemanha: 0,1765 e 0,2012.

```sql
-- (c) Teste de robustez: e se "voltar" só contasse em OUTRO DIA (calendário de São Paulo) dentro de 7 dias da primeira conversa?
WITH base AS (SELECT usuario_id, primeira_vez_utc, voltou_7d FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel),
     outro_dia AS (SELECT b.usuario_id FROM base b
                   WHERE EXISTS (SELECT 1 FROM silver.fato_conversa c
                                 WHERE c.pais = 'Brazil' AND c.usuario_id = b.usuario_id
                                   AND c.inicio_utc > b.primeira_vez_utc AND c.inicio_utc <= b.primeira_vez_utc + interval '7 days'
                                   AND timezone('America/Sao_Paulo', c.inicio_utc)::date > timezone('America/Sao_Paulo', b.primeira_vez_utc)::date))
SELECT count(*) AS elegiveis,
       count(*) FILTER (WHERE voltou_7d) AS voltaram_definicao_atual, round(100.0 * count(*) FILTER (WHERE voltou_7d) / count(*), 1) AS pct_atual,
       count(*) FILTER (WHERE usuario_id IN (SELECT usuario_id FROM outro_dia)) AS voltaram_em_outro_dia,
       round(100.0 * count(*) FILTER (WHERE usuario_id IN (SELECT usuario_id FROM outro_dia)) / count(*), 1) AS pct_outro_dia
FROM base;
```
**Passo a passo:** conta quem tem uma conversa em um **dia de calendário posterior** ao da primeira, ainda dentro dos 7 dias. Responde à pergunta "voltar duas horas depois, no mesmo dia, é retenção?".
**Deve dar:** 2.234 · 530 (23,7%) · **371 (16,6%)**. Dos 530 que voltam, 59 voltam em menos de 1 hora, 172 entre 1 e 6 horas, 125 entre 6 e 24 horas e 174 depois de mais de 1 dia. Ou seja, **o 23,7% inclui retornos no mesmo dia**; contando só outro dia, o retorno é de 16,6%.

## 1.4 Conversas e conversas por pessoa
**Na tela:** "11.621" e "4,6 por pessoa".
```sql
-- Conversas na silver e na gold, e a média por pessoa.
SELECT (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')   AS conversas_silver,
       (SELECT conversas FROM gold.pais WHERE pais = 'Brazil')             AS conversas_gold,
       round((SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')::numeric
           / (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil'), 1) AS conversas_por_pessoa;
```
**Passo a passo:** conta as linhas de `fato_conversa` (já sem as cópias exatas) e divide pelo número de pessoas.
**Deve dar:** 11.621 · 11.621 · 4,6 (Alemanha: 28.975 · 28.975 · 6,4).

## 1.5 Recusa na primeira resposta
**Na tela:** "8,9%", "198 de 2.234 pessoas". Em países sem texto a tela mostra "—".
```sql
-- Entre as pessoas elegíveis com texto, quantas receberam recusa ou desculpa na primeira resposta.
WITH s AS (SELECT count(*) FILTER (WHERE recusa) AS com, count(*) AS total
           FROM silver.fato_usuario WHERE elegivel AND recusa IS NOT NULL AND pais = 'Brazil'),
     g AS (SELECT sum(elegiveis) FILTER (WHERE nivel = 'Com recusa') AS com, sum(elegiveis) AS total
           FROM gold.agg_retorno_fator WHERE pais = 'Brazil' AND fator = 'recusa')
SELECT s.com, s.total, round(s.com::numeric / nullif(s.total, 0), 4) AS taxa_recusa,
       (s.com = coalesce(g.com, 0) AND s.total = coalesce(g.total, 0)) AS bate_com_gold
FROM s, g;
```
**Passo a passo:** `recusa` é verdadeiro quando o começo da primeira resposta casa os padrões de recusa/desculpa, falso quando não casa, e **vazio** quando o país não tem texto. `recusa IS NOT NULL` tira quem não tem texto.
**Deve dar:** 198 · 2.234 · 0,0886 · `t`. Alemanha: 0 · 0 · vazio · `t` (sem texto, o número não existe e a tela mostra "—").

## 1.6 Voltou em 24 horas
**Na tela:** "15,9%", "356 de 2.234".
```sql
-- Igual ao retorno em 7 dias, mas contando quem voltou em até 24 horas.
WITH s AS (SELECT count(*) FILTER (WHERE elegivel)                  AS n,
                  count(*) FILTER (WHERE elegivel AND voltou_24h)   AS v
           FROM silver.fato_usuario WHERE pais = 'Brazil'),
     g AS (SELECT usuarios_elegiveis AS n, voltaram_24h AS v FROM gold.pais WHERE pais = 'Brazil')
SELECT s.n AS elegiveis, s.v AS voltaram_24h, round(s.v::numeric / s.n, 4) AS taxa,
       (s.n = g.n AND s.v = g.v) AS bate_com_gold
FROM s, g;
```
**Passo a passo:** mesma base (elegíveis), trocando `voltou_7d` por `voltou_24h` (nova sessão em até 24 h da primeira vez).
**Deve dar:** 2.234 · 356 · 0,1594 · `t` (Alemanha: 3.835 · 524 · 0,1366 · `t`).

## 1.7 Concentração do uso (as 10 pessoas mais ativas)
**Na tela:** "32,3%" das conversas vêm das 10 pessoas mais ativas.
```sql
-- Conta as conversas de cada pessoa, soma as 10 maiores e divide pelo total.
WITH u AS (SELECT usuario_id, count(*) AS n FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY 1),
     s AS (SELECT (SELECT sum(n) FROM (SELECT n FROM u ORDER BY n DESC LIMIT 10) x) AS top10,
                  (SELECT sum(n) FROM u) AS total)
SELECT top10 AS conversas_das_10_mais_ativas, total AS conversas, round(top10::numeric / total, 4) AS top10_pct,
       (round(top10::numeric / total, 4) = (SELECT round(top10_pct, 4) FROM gold.pais WHERE pais = 'Brazil')) AS bate_com_gold
FROM s;
```
**Passo a passo:** `u` é "quantas conversas cada pessoa teve"; ordena da maior para a menor, pega as 10 primeiras e soma.
**Deve dar:** 3.751 · 11.621 · 0,3228 · `t` (Alemanha: 10.276 · 28.975 · 0,3547 · `t`). A tela avisa "uso concentrado" a partir de 25%.

## 1.8 "A história em poucas frases" (os 8 passos)
Cada passo é um número grande + uma frase gerada a partir dos números das outras seções. Onde conferir cada um:

| Passo | Número na tela | Onde está a consulta |
|---|---|---|
| 1 | 23,7% ("cerca de 24 em cada 100") | 1.3 |
| 2 | Voltou em 24 h (15,9%) e "92% dos retornos de 30 dias já ocorrem em 7" | 1.6 e a consulta abaixo |
| 3 | Saudação: −8,1 pp | 3.2 (efeito ajustado) |
| 4 | Recusa: −9,6 pp | 3.2 (efeito ajustado) |
| 5 | "+2,2 pp se tratássemos saudação e recusa como as demais" | consulta abaixo |
| 6 | GPT-4 24% × GPT-3.5 23% e a faixa de recusa por versão | 1.10 |
| 7 | Pico de uso às 18h e a parcela no expediente, na madrugada e no fim de semana | 1.12 |
| 8 | 10 mais ativas = 32,3% e 59,9% das pessoas têm uma só conversa | 1.7 e 1.14 |

```sql
-- Passo 2: dos que voltam em até 30 dias, que parte já voltou em até 7?
SELECT max(voltaram) FILTER (WHERE dias = 7)  AS voltaram_ate_7d,
       max(voltaram) FILTER (WHERE dias = 30) AS voltaram_ate_30d,
       round(max(voltaram) FILTER (WHERE dias = 7)::numeric / max(voltaram) FILTER (WHERE dias = 30), 4) AS parcela_que_volta_em_7d
FROM gold.agg_curva_retorno WHERE pais = 'Brazil' AND dias IN (7, 30);
```
**Deve dar:** 489 · 533 · 0,9174 (os "92%" da tela).

```sql
-- Passo 5: quanto o retorno subiria, em pontos, se quem abre com saudação ou recebe recusa voltasse como os demais.
-- Para cada efeito: |efeito| × (pessoas no grupo ÷ pessoas elegíveis). Só entram os efeitos cujo intervalo fica todo abaixo de zero.
SELECT round(sum(abs(e.efeito_pp) * e.n_tratados::numeric / p.usuarios_elegiveis), 1) AS impacto_pp,
       round(sum(abs(e.ic_hi)     * e.n_tratados::numeric / p.usuarios_elegiveis), 1) AS impacto_minimo_pp,
       round(sum(abs(e.ic_lo)     * e.n_tratados::numeric / p.usuarios_elegiveis), 1) AS impacto_maximo_pp
FROM gold.efeito_fator e JOIN gold.pais p ON p.pais = e.pais
WHERE e.pais = 'Brazil' AND e.ic_hi < 0
  AND ((e.fator = 'Tema do primeiro pedido' AND e.contraste LIKE 'Saudação%') OR e.fator = 'Recusa na primeira resposta');
```
**Deve dar:** 2,2 pp (de 0,5 a 4,0). Vale **só se o efeito fosse causal**, e a tela avisa isso. Os dois grupos se sobrepõem um pouco, então é uma estimativa por cima.

## 1.9 Retorno por mês (o gráfico de linha) e a frase de tendência
**Na tela:** a linha mensal (mai./2023 = 22,3% … abr./2024 = 21,1%) com faixa de intervalo, e a frase "não dá para dizer que está melhorando nem piorando".
```sql
-- Agrupa as pessoas elegíveis pelo mês da primeira vez (no fuso do país) e compara com a gold, mês a mês.
WITH s AS (SELECT date_trunc('month', timezone(d.fuso, u.primeira_vez_utc))::date AS mes,
                  count(*) AS elegiveis, count(*) FILTER (WHERE u.voltou_7d) AS voltaram
           FROM silver.fato_usuario u JOIN silver.dim_pais d ON d.pais = u.pais
           WHERE u.pais = 'Brazil' AND u.elegivel
           GROUP BY 1),
     g AS (SELECT mes, sum(elegiveis) AS elegiveis, sum(voltaram_7d) AS voltaram
           FROM gold.agg_retorno_mes_fator WHERE pais = 'Brazil' AND fator = 'modelo'
           GROUP BY mes)
SELECT mes, s.elegiveis, s.voltaram, round(s.voltaram::numeric / s.elegiveis, 4) AS retorno,
       (s.elegiveis = g.elegiveis AND s.voltaram = g.voltaram) AS bate_com_gold
FROM s FULL JOIN g USING (mes)
ORDER BY mes;
```
**Passo a passo:** `timezone(fuso, ...)` converte de UTC para o fuso do país antes de achar o mês. A gold guarda esse retorno repartido por fator; somar o fator `modelo` reconstitui todas as pessoas elegíveis.
**Deve dar:** 12 meses, todos `t`. Mai./2023: 282 · 63 · 0,2234; set./2023: 125 · 39 · 0,3120; abr./2024: 185 · 39 · 0,2108.

```sql
-- A frase de tendência: compara a 1ª metade dos meses com a 2ª metade e diz "estável" se a margem de erro inclui zero.
WITH s AS (SELECT date_trunc('month', timezone(d.fuso, u.primeira_vez_utc))::date AS mes, count(*) AS n, count(*) FILTER (WHERE u.voltou_7d) AS v
           FROM silver.fato_usuario u JOIN silver.dim_pais d ON d.pais = u.pais WHERE u.pais = 'Brazil' AND u.elegivel GROUP BY 1),
     m AS (SELECT mes, n, v, row_number() OVER (ORDER BY mes) AS rn, count(*) OVER () AS total FROM s),
     h AS (SELECT (rn > floor(total / 2.0)) AS segunda_metade, min(mes) AS de, max(mes) AS ate, sum(n) AS n, sum(v) AS v FROM m GROUP BY 1),
     a AS (SELECT * FROM h WHERE NOT segunda_metade), b AS (SELECT * FROM h WHERE segunda_metade),
     c AS (SELECT a.de AS de1, a.ate AS ate1, b.de AS de2, b.ate AS ate2, a.v::numeric / a.n AS p1, b.v::numeric / b.n AS p2,
                  sqrt((a.v::numeric/a.n) * (1 - a.v::numeric/a.n) / a.n + (b.v::numeric/b.n) * (1 - b.v::numeric/b.n) / b.n) AS ep FROM a, b)
SELECT de1 AS metade1_de, ate1 AS metade1_ate, round(p1, 4) AS retorno_metade1,
       de2 AS metade2_de, ate2 AS metade2_ate, round(p2, 4) AS retorno_metade2,
       round(100 * (p2 - p1), 2) AS diferenca_pp, round(100 * 1.96 * ep, 2) AS margem_pp,
       CASE WHEN (p2 - p1) - 1.96 * ep > 0 THEN 'sobe' WHEN (p2 - p1) + 1.96 * ep < 0 THEN 'cai' ELSE 'estavel' END AS tendencia
FROM c;
```
**Passo a passo:** divide os meses em duas metades (6 e 6), soma pessoas e retornos em cada uma e compara as duas taxas. Se a diferença **menos** a margem de erro ainda é maior que zero, "sobe"; se a diferença **mais** a margem é menor que zero, "cai"; senão, "estável".
**Deve dar:** 22,5% (mai. a out./2023) · 25,0% (nov./2023 a abr./2024) · diferença +2,45 pp, margem ±3,53 pp · **estável**.

## 1.10 Comparação entre modelos
**Na tela:** cartões por família (GPT-4 e GPT-3.5) e barras por versão, com retorno em 7 dias e recusa.
```sql
-- Por FAMÍLIA do modelo (GPT-4 ou GPT-3.5): retorno em 7 dias (pessoas) e recusa (conversas com texto).
WITH u AS (SELECT CASE WHEN modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END AS familia,
                  count(*) FILTER (WHERE elegivel) AS el, count(*) FILTER (WHERE elegivel AND voltou_7d) AS v
           FROM silver.fato_usuario WHERE pais = 'Brazil' GROUP BY 1),
     c AS (SELECT CASE WHEN modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END AS familia,
                  count(*) FILTER (WHERE recusa IS NOT NULL) AS texto, count(*) FILTER (WHERE recusa) AS rec
           FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY 1)
SELECT u.familia, u.el AS elegiveis, u.v AS voltaram, round(u.v::numeric / u.el, 4) AS retorno_7d,
       c.texto AS conversas_com_texto, c.rec AS com_recusa, round(c.rec::numeric / nullif(c.texto, 0), 4) AS recusa,
       (u.el = (SELECT elegiveis FROM gold.agg_retorno_fator WHERE pais = 'Brazil' AND fator = 'modelo' AND nivel = u.familia)
        AND u.v = (SELECT voltaram_7d FROM gold.agg_retorno_fator WHERE pais = 'Brazil' AND fator = 'modelo' AND nivel = u.familia)
        AND c.texto = (SELECT sum(conversas_texto) FROM gold.agg_recusa_modelo g WHERE g.pais = 'Brazil' AND (g.modelo LIKE 'gpt-4%') = (u.familia = 'GPT-4'))
        AND c.rec = (SELECT sum(com_recusa) FROM gold.agg_recusa_modelo g WHERE g.pais = 'Brazil' AND (g.modelo LIKE 'gpt-4%') = (u.familia = 'GPT-4'))) AS bate_com_gold
FROM u JOIN c ON c.familia = u.familia ORDER BY u.familia DESC;
```
**Passo a passo:** o retorno conta **pessoas** (pelo modelo da primeira conversa); a recusa conta **conversas** (de cada modelo). São bases diferentes, por isso há duas partes unidas pela família.
**Deve dar:** GPT-4: 956 · 231 · 0,2416 · 3.900 · 249 · 0,0638 · `t`. GPT-3.5: 1.278 · 299 · 0,2340 · 7.721 · 662 · 0,0857 · `t`.

```sql
-- Por VERSÃO do modelo (as barras): o mesmo cálculo, uma linha por versão.
WITH u AS (SELECT modelo, count(*) FILTER (WHERE elegivel) AS el,
                  count(*) FILTER (WHERE elegivel AND voltou_7d) AS v
           FROM silver.fato_usuario WHERE pais = 'Brazil' GROUP BY modelo),
     c AS (SELECT modelo, count(*) FILTER (WHERE recusa IS NOT NULL) AS texto,
                  count(*) FILTER (WHERE recusa) AS rec
           FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY modelo)
SELECT u.modelo, u.el AS elegiveis, round(u.v::numeric / nullif(u.el, 0), 4) AS retorno_7d,
       c.texto AS conversas_com_texto, round(c.rec::numeric / nullif(c.texto, 0), 4) AS recusa,
       (u.el = g.elegiveis AND u.v = g.voltaram_7d AND c.texto = g.conversas_texto AND c.rec = g.com_recusa) AS bate_com_gold
FROM u JOIN c ON c.modelo = u.modelo
JOIN gold.agg_recusa_modelo g ON g.pais = 'Brazil' AND g.modelo = u.modelo
ORDER BY u.el DESC;
```
**Deve dar:** seis versões, todas `t`. Exemplos: `gpt-3.5-turbo-0613`: 894 · 0,2304 · recusa 0,0381; `gpt-4-1106-preview`: 433 · 0,2794 · 0,0760; `gpt-3.5-turbo-0301`: 343 · 0,2391 · 0,1312. A "faixa de recusa por versão" do passo 6 é de 2,6% a 13,1%. Na Alemanha a recusa fica vazia (sem texto).

## 1.11 Curva de retorno (24 horas, 7 dias, 30 dias)
**Na tela:** os pontos "16,0% em 1 dia, 24,0% em 7, 26,1% em 30" (Visão geral e Coortes).
```sql
-- Para cada prazo (1, 7 e 30 dias), quantas pessoas com 30 dias de janela completa voltaram até ali.
WITH s AS (SELECT g.d AS dias, count(*) AS usuarios,
                  count(*) FILTER (WHERE u.dias_ate_voltar <= g.d) AS voltaram
           FROM silver.fato_usuario u CROSS JOIN (VALUES (1.0), (7.0), (30.0)) AS g(d)
           WHERE u.pais = 'Brazil' AND u.janela_30d
           GROUP BY g.d)
SELECT s.dias, s.usuarios, s.voltaram, round(s.voltaram::numeric / s.usuarios, 4) AS taxa,
       (s.usuarios = c.usuarios AND s.voltaram = c.voltaram) AS bate_com_gold
FROM s JOIN gold.agg_curva_retorno c ON c.pais = 'Brazil' AND c.dias = s.dias
ORDER BY s.dias;
```
**Passo a passo:** `dias_ate_voltar` é o tempo entre a primeira vez e a volta. `VALUES` repete a mesma conta para três prazos. A curva inteira (14 pontos) usa a mesma regra.
**Deve dar:** 2.039 pessoas em todas as linhas; voltaram 326, 489 e 533; taxas 0,1599, 0,2398 e 0,2614; tudo `t`.
**Por que 24,0% e não 23,7% aos 7 dias:** a curva usa só quem tem **30 dias** de janela (2.039 pessoas); o cartão usa a janela de **7 dias** (2.234). São bases diferentes, e a tela avisa.

## 1.12 Uso por dia e hora (mapa de calor)
**Na tela:** o mapa, "pico às 18h", "35,5% no expediente", "20,1% na madrugada", "29,0% no fim de semana".
```sql
-- Conta as conversas por dia da semana e hora (no fuso do país) e compara célula por célula com a gold.
WITH s AS (SELECT extract(isodow FROM timezone(d.fuso, f.inicio_utc))::int AS dia,
                  extract(hour   FROM timezone(d.fuso, f.inicio_utc))::int AS hora,
                  count(*) AS n
           FROM silver.fato_conversa f JOIN silver.dim_pais d ON d.pais = f.pais
           WHERE f.pais = 'Brazil' GROUP BY 1, 2)
SELECT sum(n) AS conversas,
       round(sum(n) FILTER (WHERE dia <= 5 AND hora BETWEEN 9 AND 17)::numeric / sum(n), 4) AS pct_expediente,
       (SELECT sum(conversas) FROM gold.agg_uso_hora WHERE pais = 'Brazil') AS conversas_gold,
       (SELECT count(*) FROM s FULL JOIN (SELECT dia_semana, hora, conversas FROM gold.agg_uso_hora WHERE pais = 'Brazil') g
              ON g.dia_semana = s.dia AND g.hora = s.hora
        WHERE s.n IS DISTINCT FROM g.conversas) AS celulas_diferentes
FROM s;
```
**Passo a passo:** `isodow` dá o dia da semana (1 = segunda … 7 = domingo). "Expediente" é segunda a sexta, das 9h às 17h59. `celulas_diferentes` conta as células (dia × hora) em que silver e gold discordam; tem de ser **0**.
**Deve dar:** 11.621 · 0,3555 · 11.621 · 0 (Alemanha: 28.975 · 0,3048 · 28.975 · 0).

```sql
-- As faixas do texto da tela, com o que se esperaria se o uso fosse igual em todas as horas da semana.
WITH s AS (SELECT extract(isodow FROM timezone(d.fuso, f.inicio_utc))::int AS dia, extract(hour FROM timezone(d.fuso, f.inicio_utc))::int AS hora, count(*) AS n
           FROM silver.fato_conversa f JOIN silver.dim_pais d ON d.pais = f.pais WHERE f.pais = 'Brazil' GROUP BY 1, 2),
     h AS (SELECT hora, sum(n) AS n FROM s GROUP BY hora)
SELECT (SELECT hora FROM h ORDER BY n DESC LIMIT 1) AS hora_do_pico,
       round(sum(n) FILTER (WHERE dia <= 5 AND hora BETWEEN 9 AND 17)::numeric / sum(n), 4) AS expediente, round(45.0 / 168, 4) AS expediente_esperado,
       round(sum(n) FILTER (WHERE hora >= 22 OR hora < 6)::numeric / sum(n), 4) AS madrugada, round(8.0 / 24, 4) AS madrugada_esperada,
       round(sum(n) FILTER (WHERE dia >= 6)::numeric / sum(n), 4) AS fim_de_semana, round(2.0 / 7, 4) AS fim_de_semana_esperado
FROM s;
```
**Passo a passo:** o "esperado" é a parcela das horas da semana que a faixa ocupa (expediente: 45 de 168 horas; madrugada: 8 de 24; fim de semana: 2 de 7). A tela diz "acima" ou "abaixo" quando a diferença passa de 10%.
**Deve dar:** pico às 18h · expediente 0,3555 (esperado 0,2679) · madrugada 0,2006 (esperado 0,3333) · fim de semana 0,2898 (esperado 0,2857).

## 1.13 GPT-4 por mês
**Na tela:** o gráfico "modelo no tempo" (GPT-4 era 15,7% em abr./2023, 0% de jul. a out./2023 e mais de 90% em 2024).
```sql
-- Por mês: quantas conversas e quantas foram com GPT-4 (modelo que começa com 'gpt-4').
WITH s AS (SELECT date_trunc('month', timezone(d.fuso, f.inicio_utc))::date AS mes, count(*) AS conversas,
                  count(*) FILTER (WHERE f.modelo LIKE 'gpt-4%') AS gpt4
           FROM silver.fato_conversa f JOIN silver.dim_pais d ON d.pais = f.pais
           WHERE f.pais = 'Brazil' GROUP BY 1)
SELECT s.mes, s.conversas, s.gpt4, round(s.gpt4::numeric / s.conversas, 4) AS pct_gpt4,
       (s.conversas = g.conversas AND s.gpt4 = g.conversas_gpt4) AS bate_com_gold
FROM s JOIN gold.agg_modelo_mes g ON g.pais = 'Brazil' AND g.mes = s.mes
ORDER BY s.mes;
```
**Passo a passo:** conta conversas por mês no fuso do país e separa as de GPT-4.
**Deve dar:** 13 meses, todos `t`. Abr./2023: 1.291 · 203 · 0,1572; jul. a out./2023: 0 de GPT-4; dez./2023: 678 · 513 · 0,7566; abr./2024: 713 · 661 · 0,9271.

## 1.14 Concentração do uso: faixas e retorno sem as 10 mais ativas
**Na tela:** o gráfico "pessoas × conversas" por faixa e as frases "59,9% das pessoas têm uma só conversa" e "retirando as 10 mais ativas, o retorno vai de 23,7% para 23,5%".
```sql
-- Quantas pessoas têm 1, 2-3, 4-10 ou 11+ conversas, e que parte das conversas cada faixa responde.
WITH u AS (SELECT usuario_id, count(*) AS n FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY 1),
     f AS (SELECT CASE WHEN n = 1 THEN 1 WHEN n <= 3 THEN 2 WHEN n <= 10 THEN 3 ELSE 4 END AS ordem,
                  CASE WHEN n = 1 THEN '1' WHEN n <= 3 THEN '2-3' WHEN n <= 10 THEN '4-10' ELSE '11+' END AS faixa,
                  count(*) AS pessoas, sum(n) AS conversas FROM u GROUP BY 1, 2)
SELECT f.faixa, f.pessoas, round(f.pessoas::numeric / sum(f.pessoas) OVER (), 4) AS pct_pessoas,
       f.conversas, round(f.conversas::numeric / sum(f.conversas) OVER (), 4) AS pct_conversas,
       (f.pessoas = g.usuarios AND f.conversas = g.conversas) AS bate_com_gold
FROM f JOIN gold.agg_concentracao g ON g.pais = 'Brazil' AND g.ordem = f.ordem
ORDER BY f.ordem;
```
**Passo a passo:** `u` conta as conversas de cada pessoa; o `CASE` coloca cada pessoa na sua faixa; `sum(...) OVER ()` calcula a parcela de cada faixa no total.
**Deve dar:** 1 conversa: 1.516 pessoas (0,5992) · 1.516 conversas (0,1305); 2-3: 556 · 1.285; 4-10: 308 · 1.796; 11+: 150 pessoas (0,0593) e 7.024 conversas (0,6044). Todas `t`. **150 pessoas (5,9%) fazem 60% das conversas.**

```sql
-- O retorno em 7 dias com todas as pessoas e sem as 10 mais ativas, e a parcela de pessoas com uma só conversa.
WITH u AS (SELECT usuario_id, count(*) AS n FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY 1),
     top AS (SELECT usuario_id FROM u ORDER BY n DESC, usuario_id LIMIT 10),
     s AS (SELECT count(*) FILTER (WHERE elegivel) AS el, count(*) FILTER (WHERE elegivel AND voltou_7d) AS v,
                  count(*) FILTER (WHERE elegivel AND usuario_id NOT IN (SELECT usuario_id FROM top)) AS el_sem,
                  count(*) FILTER (WHERE elegivel AND voltou_7d AND usuario_id NOT IN (SELECT usuario_id FROM top)) AS v_sem
           FROM silver.fato_usuario WHERE pais = 'Brazil')
SELECT round(v::numeric / el, 4) AS retorno_com_todos, round(v_sem::numeric / el_sem, 4) AS retorno_sem_as_10_mais_ativas,
       round((SELECT count(*) FILTER (WHERE n = 1) FROM u)::numeric / (SELECT count(*) FROM u), 4) AS pessoas_com_1_conversa,
       (el_sem = g.elegiveis_sem_top10 AND v_sem = g.voltaram_sem_top10) AS bate_com_gold
FROM s, gold.pais g WHERE g.pais = 'Brazil';
```
**Passo a passo:** acha as 10 pessoas com mais conversas (`top`) e refaz o retorno deixando essas 10 de fora, para mostrar que os "superusuários" quase não mexem no resultado.
**Deve dar:** 0,2372 · 0,2345 · 0,5992 · `t`.

## 1.15 Comparação entre países e média geral
**Na tela:** as barras de países e a "média geral" (21,5%).
```sql
-- Refaz o retorno de TODOS os países na silver e compara com a gold. Mostra quantos países entram e quantos divergem.
WITH s AS (SELECT pais, count(*) FILTER (WHERE elegivel) AS el, count(*) FILTER (WHERE elegivel AND voltou_7d) AS v
           FROM silver.fato_usuario GROUP BY pais),
     g AS (SELECT pais, sum(elegiveis) AS el, sum(voltaram_7d) AS v
           FROM gold.agg_retorno_semana GROUP BY pais)
SELECT count(*) FILTER (WHERE s.el >= 30)                                      AS paises_com_30_ou_mais,
       count(*) FILTER (WHERE s.el >= 30 AND (s.el <> g.el OR s.v <> g.v))     AS paises_divergentes,
       round((SELECT sum(v)::numeric / sum(el) FROM s), 4)                     AS media_geral
FROM s JOIN g USING (pais);
```
**Passo a passo:** só países com 30 ou mais elegíveis aparecem na tela. A média geral soma voltaram e elegíveis de **todos** os países (cada pessoa com o mesmo peso). Esta consulta **não depende** do país escolhido.
**Deve dar:** 120 países · 0 divergentes · 0,2150.

```sql
-- Os 5 países com mais pessoas elegíveis, com o retorno de cada um (as maiores barras da tela).
WITH s AS (SELECT pais, count(*) FILTER (WHERE elegivel) AS el, count(*) FILTER (WHERE elegivel AND voltou_7d) AS v FROM silver.fato_usuario GROUP BY pais)
SELECT pais, el AS elegiveis, v AS voltaram, round(v::numeric / el, 4) AS retorno FROM s WHERE el >= 30 ORDER BY el DESC LIMIT 5;
```
**Deve dar:** China 24.866 · 0,2410; Russia 20.966 · 0,2671; United States 19.751 · 0,2088; Hong Kong 9.778 · 0,2142; India 6.594 · 0,1421.

---

# 2. Coortes semanais

A curva de retorno (24 h, 7 e 30 dias) desta tela é a mesma da seção **1.11**. O mapa de calor "por mês" é a seção **1.9** e o "por semana" é a consulta abaixo.

## 2.1 Pessoas novas e retorno por semana (a semana do incidente)
**Na tela:** o gráfico de pessoas novas por semana, o mapa de calor semanal e a semana de 20/11/2023 do PDF.
```sql
-- Novos, elegíveis e quem voltou, por semana de chegada (segunda a domingo, no fuso do país).
WITH s AS (SELECT semana, count(*) AS novos, count(*) FILTER (WHERE elegivel) AS elegiveis,
                  count(*) FILTER (WHERE elegivel AND voltou_7d) AS voltaram
           FROM silver.fato_usuario WHERE pais = 'Brazil' GROUP BY semana)
SELECT s.semana, s.novos, s.elegiveis, s.voltaram, round(s.voltaram::numeric / nullif(s.elegiveis, 0), 4) AS retorno,
       (s.novos = g.novos AND s.elegiveis = g.elegiveis AND s.voltaram = g.voltaram_7d) AS bate_com_gold
FROM s JOIN gold.agg_retorno_semana g ON g.pais = 'Brazil' AND g.semana = s.semana
WHERE s.semana BETWEEN '2023-11-06' AND '2023-11-27'
ORDER BY s.semana;
```
**Passo a passo:** `semana` já vem calculada na silver (a segunda-feira da semana da primeira vez). O `WHERE` final escolhe as semanas de 06/11 a 27/11/2023 (a do PDF é 20/11); troque as datas para ver outras. Retire o `WHERE` para ver todas.
**Deve dar (Brasil):** 06/11: 48 · 12 · 0,2500; 13/11: 55 · 16 · 0,2909; 20/11: 68 · 14 · 0,2059; 27/11: 67 · 14 · 0,2090; todas `t`. A Alemanha dá 105, 80, 132 e 108 pessoas nessas semanas.
Semanas com menos de 30 elegíveis aparecem na tela como "amostra pequena" e sem taxa; a conta aqui continua válida. Os números do PDF (1.210 novos, 31% → 18%) são do exemplo do enunciado, não desta base: o que o incidente mostra é o **erro de código** que dobra os novos, explicado em [`INCIDENTE.md`](INCIDENTE.md).

## 2.2 Decomposição: chegou gente diferente ou a mesma gente voltou diferente?
**Na tela:** "mai./2023 → abr./2024: de 22,3% para 21,1% (−1,3 pp): mix +2,2 · taxa −2,0 · interação −1,5".
```sql
-- Separa a variação do retorno entre dois meses em três partes, olhando o tema do primeiro pedido:
--   mix       = mudou QUEM chegou (a proporção de cada tema)
--   taxa      = mudou o retorno DENTRO de cada tema
--   interação = as duas mudanças ao mesmo tempo
-- Troque as duas datas da linha "p" para comparar outros meses.
WITH x AS (SELECT date_trunc('month', timezone(d.fuso, u.primeira_vez_utc))::date AS mes, t.tema AS nivel, count(*) AS n, count(*) FILTER (WHERE u.voltou_7d) AS v
           FROM silver.fato_usuario u JOIN silver.dim_pais d ON d.pais = u.pais JOIN silver.dim_tema t ON t.tema_id = u.tema_id
           WHERE u.pais = 'Brazil' AND u.elegivel GROUP BY 1, 2),
     p AS (SELECT DATE '2023-05-01' AS de, DATE '2024-04-01' AS para),
     t0 AS (SELECT sum(n) AS n, sum(v) AS v FROM x, p WHERE mes = p.de),
     t1 AS (SELECT sum(n) AS n, sum(v) AS v FROM x, p WHERE mes = p.para),
     k AS (SELECT DISTINCT nivel FROM x, p WHERE mes IN (p.de, p.para)),
     w AS (SELECT k.nivel,
                  coalesce(a.n, 0)::numeric / t0.n AS w0, coalesce(b.n, 0)::numeric / t1.n AS w1,
                  CASE WHEN a.n > 0 THEN a.v::numeric / a.n ELSE t0.v::numeric / t0.n END AS r0,
                  CASE WHEN b.n > 0 THEN b.v::numeric / b.n ELSE t1.v::numeric / t1.n END AS r1
           FROM k CROSS JOIN t0 CROSS JOIN t1 CROSS JOIN p
           LEFT JOIN x a ON a.nivel = k.nivel AND a.mes = p.de LEFT JOIN x b ON b.nivel = k.nivel AND b.mes = p.para)
SELECT t0.n AS elegiveis_de, round(100.0 * t0.v / t0.n, 2) AS retorno_de, t1.n AS elegiveis_para, round(100.0 * t1.v / t1.n, 2) AS retorno_para,
       round(100.0 * (t1.v::numeric / t1.n - t0.v::numeric / t0.n), 2) AS variacao_pp,
       round(100 * sum((w1 - w0) * r0), 2) AS mix_pp, round(100 * sum(w0 * (r1 - r0)), 2) AS taxa_pp, round(100 * sum((w1 - w0) * (r1 - r0)), 2) AS interacao_pp
FROM w, t0, t1 GROUP BY t0.n, t0.v, t1.n, t1.v;
```
**Passo a passo:** `x` conta, por mês e tema, as pessoas e quem voltou. Para cada tema, `w0` e `w1` são a sua parcela entre as pessoas de cada mês, e `r0` e `r1` o seu retorno. As três partes são: **mix** = Σ(w1 − w0) × r0, **taxa** = Σ w0 × (r1 − r0), **interação** = Σ(w1 − w0) × (r1 − r0). Elas somam exatamente a variação (a API confere isso com `soma_confere`).
**Deve dar:** 282 → 185 pessoas · 22,34% → 21,08% · variação −1,26 pp = **mix +2,22 · taxa −2,02 · interação −1,47** (soma: −1,27, a diferença é só arredondamento). Com 282 e 185 pessoas, nenhuma das três partes se distingue do ruído: o retorno ficou praticamente estável.
### Exemplo semanal (a semana de 20/11/2023)
O PDF pede uma **semana**. O painel decompõe por mês porque uma semana tem poucas pessoas; a mesma conta, por semana, é esta:
```sql
-- Mesma decomposição, com a semana de chegada no lugar do mês. Troque as duas datas (sempre uma segunda-feira) para comparar outras semanas.
WITH x AS (SELECT u.semana AS per, t.tema AS nivel, count(*) AS n, count(*) FILTER (WHERE u.voltou_7d) AS v
           FROM silver.fato_usuario u JOIN silver.dim_tema t ON t.tema_id = u.tema_id
           WHERE u.pais = 'Brazil' AND u.elegivel GROUP BY 1, 2),
     p AS (SELECT DATE '2023-11-13' AS de, DATE '2023-11-20' AS para),
     t0 AS (SELECT sum(n) AS n, sum(v) AS v FROM x, p WHERE per = p.de),
     t1 AS (SELECT sum(n) AS n, sum(v) AS v FROM x, p WHERE per = p.para),
     k AS (SELECT DISTINCT nivel FROM x, p WHERE per IN (p.de, p.para)),
     w AS (SELECT k.nivel, coalesce(a.n, 0)::numeric / t0.n AS w0, coalesce(b.n, 0)::numeric / t1.n AS w1,
                  CASE WHEN a.n > 0 THEN a.v::numeric / a.n ELSE t0.v::numeric / t0.n END AS r0,
                  CASE WHEN b.n > 0 THEN b.v::numeric / b.n ELSE t1.v::numeric / t1.n END AS r1
           FROM k CROSS JOIN t0 CROSS JOIN t1 CROSS JOIN p
           LEFT JOIN x a ON a.nivel = k.nivel AND a.per = p.de LEFT JOIN x b ON b.nivel = k.nivel AND b.per = p.para)
SELECT t0.n AS elegiveis_de, round(100.0 * t0.v / t0.n, 2) AS retorno_de, t1.n AS elegiveis_para, round(100.0 * t1.v / t1.n, 2) AS retorno_para,
       round(100.0 * (t1.v::numeric / t1.n - t0.v::numeric / t0.n), 2) AS variacao_pp,
       round(100 * sum((w1 - w0) * r0), 2) AS mix_pp, round(100 * sum(w0 * (r1 - r0)), 2) AS taxa_pp, round(100 * sum((w1 - w0) * (r1 - r0)), 2) AS interacao_pp,
       round(100 * 1.96 * sqrt((t0.v::numeric / t0.n) * (1 - t0.v::numeric / t0.n) / t0.n + (t1.v::numeric / t1.n) * (1 - t1.v::numeric / t1.n) / t1.n), 1) AS margem_da_variacao_pp
FROM w, t0, t1 GROUP BY t0.n, t0.v, t1.n, t1.v;
```
**Deve dar:** 55 → 68 pessoas · 29,09% → 20,59% · variação **−8,50 pp** = mix **−0,19** · taxa **−10,61** · interação **+2,30**, com margem de erro de **±15,4 pp**. Leitura: quase todo o movimento é "o retorno caiu **dentro** dos temas" (a taxa), e não "chegou gente diferente" (o mix é ≈ 0). Mas com 55 e 68 pessoas a margem (±15 pp) é maior que a queda: **não dá para distinguir de acaso**, e por isso o painel usa meses.

---

# 3. O que faz voltar

Cada linha da tela de efeitos tem duas partes:

| Parte | Em SQL? |
|---|---|
| Quantas pessoas em cada grupo (n), o retorno do grupo de comparação, o **efeito bruto** e o intervalo dele | **Sim**: seção 3.1 |
| A etiqueta "resiste à correção / indício / inconclusivo" | **Sim**: seção 3.3 (conta a partir do intervalo) |
| O **efeito ajustado** (o número grande, ex.: +8,7), o intervalo dele, "grupos parecidos?", o E-value | **Não**: é uma estimativa estatística (AIPW, regressão logística com validação cruzada) calculada em Python, em [`etl/camadas/gold/efeitos.py`](../etl/camadas/gold/efeitos.py). O SQL só **lê** o resultado guardado (seção 3.2). |

O **efeito bruto** é a diferença simples entre os dois grupos. O **ajustado** compara pessoas **parecidas** (mesmo mês, horário, sistema, navegador, estado, modelo, tema, tamanho do pedido, idioma), por isso é diferente do bruto (nos turnos: +8,7 ajustado contra +6,5 bruto). Método e limites em [`bdr/BDR-004-analise-de-efeitos.md`](bdr/BDR-004-analise-de-efeitos.md).

## 3.1 Grupos e efeito bruto (as 16 linhas de uma vez)
**Na tela:** em cada linha, "Quem foi comparado: 1.200 pessoas no grupo do fator contra 1.034 no grupo de comparação (retorno de 20,2%)" e "Efeito bruto +6,5 pp [+3,0; +10,0]".
```sql
-- Para cada efeito, divide as pessoas elegíveis em dois grupos (com o fator e sem o fator), calcula o retorno de cada um e a
-- diferença em pontos percentuais, com a margem de erro de 95%. Compara com a linha guardada na gold.
WITH b AS (SELECT u.voltou_7d::int AS y, u.modelo, u.idioma, u.turnos, u.prompt1_chars, u.resp1_chars, coalesce(u.recusa, false) AS recusa,
                  coalesce(t.tema, 'Outro') AS tema, u.hora, u.dia_semana
           FROM silver.fato_usuario u LEFT JOIN silver.dim_tema t USING (tema_id) WHERE u.pais = 'Brazil' AND u.elegivel),
     m AS (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY resp1_chars) AS resp, percentile_cont(0.5) WITHIN GROUP (ORDER BY prompt1_chars) AS pedido FROM b),
     x AS (
       SELECT 'Modelo' AS fator, 'GPT-4 em vez de GPT-3.5' AS contraste, (modelo LIKE 'gpt-4%') AS tratado, y FROM b
       UNION ALL SELECT 'Recusa na primeira resposta', 'Com recusa em vez de sem', recusa, y FROM b
       UNION ALL SELECT 'Tamanho da primeira resposta', 'Longa (>= ' || trunc(m.resp)::int || ' caracteres) em vez de curta', coalesce(b.resp1_chars >= m.resp, false), y FROM b, m
       UNION ALL SELECT 'Turnos da primeira conversa', '2 ou mais em vez de 1', turnos >= 2, y FROM b
       UNION ALL SELECT 'Tamanho do primeiro pedido', 'Longo (>= ' || trunc(m.pedido)::int || ' caracteres) em vez de curto', coalesce(b.prompt1_chars >= m.pedido, false), y FROM b, m
       UNION ALL SELECT 'Horário', 'Noite (18-23h) em vez de outros períodos', hora >= 18, y FROM b
       UNION ALL SELECT 'Dia da semana', 'Fim de semana em vez de dia útil', dia_semana >= 6, y FROM b
       UNION ALL SELECT 'Idioma', 'Inglês em vez de português', idioma = 'English', y FROM b WHERE idioma IN ('Portuguese', 'English')
       UNION ALL SELECT 'Tema do primeiro pedido', tt.tema || ' em vez de Conhecimento/pergunta', b.tema = tt.tema, y
         FROM b JOIN (SELECT DISTINCT tema FROM b WHERE tema <> 'Conhecimento/pergunta') tt ON b.tema IN (tt.tema, 'Conhecimento/pergunta')),
     g AS (SELECT fator, contraste, count(*) FILTER (WHERE tratado) AS n1, count(*) FILTER (WHERE NOT tratado) AS n0,
                  avg(y) FILTER (WHERE tratado) AS p1, avg(y) FILTER (WHERE NOT tratado) AS p0 FROM x GROUP BY 1, 2
           HAVING count(*) FILTER (WHERE tratado) >= 30 AND count(*) FILTER (WHERE NOT tratado) >= 30),   -- grupos pequenos não são estimados
     d AS (SELECT fator, contraste, n1, n0, p0, 100 * (p1 - p0) AS dif, 100 * 1.96 * sqrt(p1*(1-p1)/n1 + p0*(1-p0)/n0) AS margem FROM g)
SELECT d.fator, d.contraste, d.n1 AS n_grupo, d.n0 AS n_comparacao, round(d.p0, 4) AS retorno_comparacao,
       round(d.dif, 2) AS bruto_pp, round(d.dif - d.margem, 2) AS bruto_ic_lo, round(d.dif + d.margem, 2) AS bruto_ic_hi,
       (d.n1 = e.n_tratados AND d.n0 = e.n_controle AND round(d.dif, 2) = e.efeito_bruto_pp
        AND round(d.dif - d.margem, 2) = e.bruto_ic_lo AND round(d.dif + d.margem, 2) = e.bruto_ic_hi) AS bate_com_gold
FROM d LEFT JOIN gold.efeito_fator e ON e.pais = 'Brazil' AND e.fator = d.fator AND e.contraste = d.contraste
ORDER BY d.dif DESC;
```
**Passo a passo:**
1. `b` pega cada pessoa elegível com as características que definem os grupos (`y` = voltou em 7 dias, 1 ou 0).
2. `m` calcula as medianas do tamanho da resposta e do pedido (60 caracteres no pedido), que dividem "longo" de "curto".
3. `x` empilha, para cada fator, a lista de pessoas com `tratado` = "tem o fator" (ex.: 2 ou mais turnos). Os temas são comparados, um por vez, com "Conhecimento/pergunta".
4. `g` calcula o retorno de cada grupo (`p1` com o fator, `p0` sem) e quantas pessoas há em cada um.
5. `d` faz a diferença `p1 − p0` em pontos percentuais e a margem de erro de 95% (`1,96 × erro-padrão`).
6. O final compara com `gold.efeito_fator`. Grupos com menos de 30 pessoas não são estimados (o `HAVING` dentro de `g`, que também evita divisão por zero), por isso há 16 linhas, não 18. A ordem é do maior efeito bruto para o menor.
**Outros países:** a consulta roda (Alemanha: 4 linhas, só os fatores que não dependem de texto), mas `bate_com_gold` fica **vazio**, porque a gold só estima efeitos para o Brasil (o desafio pede o Brasil). Vale o mesmo para as seções 3.2 a 3.4.

**Deve dar:** 16 linhas, todas `t`. Exemplos: Turnos (2 ou mais em vez de 1): 1.200 · 1.034 · 0,2021 · +6,54 [+3,04; +10,04]. Saudação em vez de Conhecimento/pergunta: 386 · 531 · 0,2561 · −10,85 [−15,97; −5,72] (a tela mostra n = 917, que é 386 + 531). Recusa: 198 · 2.036 · 0,2451 · −8,85 [−14,25; −3,46]. Pedido longo: 1.119 · 1.115 · 0,2000 · +7,44 [+3,92; +10,95]. Modelo (GPT-4 em vez de GPT-3.5): 956 · 1.278 · 0,2340 · +0,77.

## 3.2 O que a gold guardou: efeito ajustado, intervalo, sobreposição, E-value
**Na tela:** "Efeito ajustado +8,7 pp [+3,3; +14,1]", "97,9% das pessoas têm chance comparável", "E-value 1,6", "Ajustado por ...", "Método ...".
```sql
-- Uma linha por efeito, exatamente como a tela mostra. Aqui o SQL só lê: a estimativa é feita em Python na carga.
SELECT fator, contraste, n_tratados, n_controle, efeito_bruto_pp, efeito_pp AS efeito_ajustado_pp, ic_lo, ic_hi,
       sobreposicao AS grupos_parecidos_pct, e_value, ajustado_por, metodo
FROM gold.efeito_fator
WHERE pais = 'Brazil'
ORDER BY abs(efeito_pp) DESC;
```
**Passo a passo:** só lê a tabela. `sobreposicao` é a parcela de pessoas com chance comparável de estar em qualquer um dos grupos (quanto mais alta, mais confiável a comparação). `e_value` diz quão forte teria de ser um fator **não medido** para anular o resultado. `ajustado_por` lista as características igualadas.
**Deve dar (turnos):** bruto +6,54 · ajustado +8,72 [+3,30; +14,14] · sobreposição 97,9 · E-value 2,26 para o efeito e **1,62 para o limite do intervalo** (`e_value_ic`, o "1,6" que a tela mostra; acrescente `e_value_ic` ao `SELECT` para vê-lo).
**Como confiar no ajustado, se ele não sai de SQL:** (1) o código é o `efeitos.py`, com semente fixa e ordem fixa das linhas, então a mesma base dá sempre o mesmo número (a conferência de **deriva** da carga acusa se mudar); (2) o bruto da seção 3.1 mostra que a base do cálculo (grupos e retornos) está certa; (3) sensibilidade e limites em [`SENSIBILIDADE.md`](SENSIBILIDADE.md) e no BDR-004. **É associação ajustada, não prova de causa.**

## 3.3 A etiqueta "resiste à correção", "indício" ou "inconclusivo"
**Na tela:** à direita de cada efeito.
```sql
-- Refaz a etiqueta a partir do efeito e do intervalo guardados. Como são 16 efeitos testados ao mesmo tempo, o limite de
-- significância 0,05 é dividido por 16 (correção de Bonferroni): só "resiste" quem tem p-valor abaixo de 0,05 / 16 = 0,003.
WITH e AS (SELECT fator, contraste, efeito_pp, ic_lo, ic_hi, count(*) OVER () AS m,
                  (ic_hi - ic_lo) / (2 * 1.96) AS ep FROM gold.efeito_fator WHERE pais = 'Brazil'),
     z AS (SELECT *, abs(efeito_pp) / ep / sqrt(2.0) AS a FROM e),
     p AS (SELECT *, 1.0 / (1 + 0.3275911 * a) AS t FROM z),
     q AS (SELECT *, 1 - (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * exp(-a * a)) AS pv FROM p)
SELECT fator, contraste, efeito_pp, ic_lo, ic_hi, round(pv::numeric, 5) AS p_valor,
       CASE WHEN pv < 0.05 / m THEN 'resiste à correção' WHEN ic_lo > 0 OR ic_hi < 0 THEN 'indício' ELSE 'inconclusivo' END AS etiqueta
FROM q
ORDER BY CASE WHEN pv < 0.05 / m THEN 0 WHEN ic_lo > 0 OR ic_hi < 0 THEN 1 ELSE 2 END, abs(efeito_pp) DESC;
```
**Passo a passo:** o erro-padrão sai da largura do intervalo (`largura ÷ (2 × 1,96)`). O `z` é o efeito dividido pelo erro-padrão. O p-valor usa a mesma aproximação da função de erro que a tela usa. Se o p-valor é menor que 0,05 ÷ 16, o efeito "resiste à correção". Se só o intervalo não toca zero, é "indício". Se toca zero, é "inconclusivo".
**Deve dar:** **resiste à correção:** Turnos (+8,72, p = 0,0016) e Tamanho do pedido (+6,33, p = 0,0030). **Indício:** Recusa (−9,58) e Saudação (−8,05). Os outros 12 efeitos: inconclusivo (o intervalo inclui zero), incluindo o Modelo (−0,55) e o Tamanho da resposta (+0,12).

## 3.4 Os 4 achados: impacto no retorno, saudação e recusa dentro de cada modelo
**Na tela:** o painel "Os 4 achados". O impacto ("+2,2 pp") é a consulta do passo 5 da seção **1.8**. As diferenças por modelo ("saudação −10,1 pp no GPT-3.5 e −11,9 pp no GPT-4") saem daqui:
```sql
-- Saudação e recusa DENTRO de cada família de modelo: retorno de cada grupo e diferença simples (sem ajuste), com margem de 95%.
WITH b AS (SELECT CASE WHEN u.modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END AS familia, u.voltou_7d,
                  f.fator, f.nivel
           FROM silver.fato_usuario u LEFT JOIN silver.dim_tema t ON t.tema_id = u.tema_id
           CROSS JOIN LATERAL (VALUES
             ('recusa', CASE WHEN u.recusa IS NULL THEN NULL WHEN u.recusa THEN 'Com recusa' ELSE 'Sem recusa' END),
             ('saudacao', CASE WHEN t.tema IS NULL THEN NULL WHEN t.tema = 'Saudação' THEN 'Saudação' ELSE 'Outro tema' END)) AS f(fator, nivel)
           WHERE u.pais = 'Brazil' AND u.elegivel AND f.nivel IS NOT NULL),
     s AS (SELECT fator, familia, nivel, count(*) AS elegiveis, count(*) FILTER (WHERE voltou_7d) AS voltaram FROM b GROUP BY 1, 2, 3),
     d AS (SELECT t.fator, t.familia, t.nivel AS grupo, t.elegiveis AS n_grupo, c.elegiveis AS n_comparacao,
                  100 * (t.voltaram::numeric / t.elegiveis - c.voltaram::numeric / c.elegiveis) AS dif,
                  100 * 1.96 * sqrt((t.voltaram::numeric/t.elegiveis)*(1-t.voltaram::numeric/t.elegiveis)/t.elegiveis
                                  + (c.voltaram::numeric/c.elegiveis)*(1-c.voltaram::numeric/c.elegiveis)/c.elegiveis) AS margem,
                  (t.elegiveis = g1.elegiveis AND t.voltaram = g1.voltaram_7d AND c.elegiveis = g2.elegiveis AND c.voltaram = g2.voltaram_7d) AS bate
           FROM s t JOIN s c ON c.fator = t.fator AND c.familia = t.familia AND c.nivel <> t.nivel
           JOIN gold.agg_estrato g1 ON g1.pais = 'Brazil' AND g1.fator = t.fator AND g1.familia = t.familia AND g1.nivel = t.nivel
           JOIN gold.agg_estrato g2 ON g2.pais = 'Brazil' AND g2.fator = c.fator AND g2.familia = c.familia AND g2.nivel = c.nivel
           WHERE t.nivel IN ('Com recusa', 'Saudação'))
SELECT fator, familia, grupo, n_grupo, n_comparacao, round(dif, 1) AS diferenca_pp, round(dif - margem, 1) AS ic_lo, round(dif + margem, 1) AS ic_hi, bate AS bate_com_gold
FROM d ORDER BY fator, familia;
```
**Passo a passo:** repete a conta do retorno por grupo, mas **separando as pessoas pela família do modelo**. A diferença é "grupo com o fator menos grupo de comparação". É uma comparação simples, **sem ajuste**, por isso a tela a chama de hipótese.
**Deve dar:** recusa no GPT-3.5: 110 contra 1.168 · −4,7 [−12,5; +3,0] (o intervalo inclui zero); recusa no GPT-4: 88 contra 868 · −14,1 [−21,3; −6,9]; saudação no GPT-3.5: 237 contra 1.041 · −10,1 [−15,4; −4,8]; saudação no GPT-4: 149 contra 807 · −11,9 [−18,3; −5,6]. Todas `t`.

## 3.5 Turnos, dispositivo, sistema, navegador e idioma × navegador
**Na tela:** as barras de retorno por número de turnos, e o painel "dispositivo e navegador" (com os botões Dispositivo, Sistema e Navegador) e o de "idioma do pedido × navegador".
```sql
-- Retorno em 7 dias de cada nível de quatro fatores simples. O CASE de cada um é a definição do nível.
WITH b AS (SELECT u.voltou_7d, f.fator, f.nivel
           FROM silver.fato_usuario u
           CROSS JOIN LATERAL (VALUES
             ('turnos_da_primeira_conversa', CASE WHEN u.turnos = 1 THEN '1 turno' WHEN u.turnos <= 3 THEN '2-3 turnos' WHEN u.turnos <= 6 THEN '4-6 turnos' ELSE '7+ turnos' END),
             ('dispositivo', CASE WHEN u.sistema IN ('Android', 'iOS') THEN 'Celular' ELSE 'Computador' END),
             ('sistema', coalesce(u.sistema, 'Outro')),
             ('navegador', coalesce(u.navegador, 'Outro'))) AS f(fator, nivel)
           WHERE u.pais = 'Brazil' AND u.elegivel),
     s AS (SELECT fator, nivel, count(*) AS elegiveis, count(*) FILTER (WHERE voltou_7d) AS voltaram FROM b GROUP BY 1, 2)
SELECT s.fator, s.nivel, s.elegiveis, s.voltaram, round(s.voltaram::numeric / s.elegiveis, 4) AS retorno,
       (s.elegiveis = g.elegiveis AND s.voltaram = g.voltaram_7d) AS bate_com_gold
FROM s JOIN gold.agg_retorno_fator g ON g.pais = 'Brazil' AND g.fator = s.fator AND g.nivel = s.nivel
ORDER BY s.fator, s.elegiveis DESC;
```
**Passo a passo:** `VALUES` cria, para cada pessoa, uma linha por fator, com o nível dela (o `CASE` define as faixas). Depois é contar quantas voltaram em cada nível. A mesma estrutura serve para qualquer outro fator de `gold.agg_retorno_fator`.
**Deve dar:** 18 linhas, todas `t`. Turnos: 1 turno 1.034 · 0,2021; 2-3: 778 · 0,2429; 4-6: 280 · 0,2536; **7 ou mais: 142 · 0,4296**. Dispositivo: Computador 1.500 · 0,2360; Celular 734 · 0,2398. Navegador: Chrome 1.624 · 0,2426; Firefox 180 · 0,3444; Safari 122 · 0,1393. Sistema: Windows 1.298 · 0,2450; Android 627 · 0,2568; iOS 107 · 0,1402; Mac 88 · 0,1591. **São hipóteses**: a medida (IP e navegador) pode distorcer os grupos de Apple.

```sql
-- Idioma do pedido × idioma do navegador: a pessoa escreve no idioma do navegador, em inglês, ou em outro?
WITH b AS (SELECT u.voltou_7d,
             CASE WHEN coalesce(u.idioma_navegador, '') = '' OR u.idioma IS NULL THEN NULL
                  WHEN split_part(u.idioma_navegador, '-', 1) = CASE u.idioma WHEN 'English' THEN 'en' WHEN 'Portuguese' THEN 'pt' WHEN 'Spanish' THEN 'es'
                       WHEN 'French' THEN 'fr' WHEN 'German' THEN 'de' WHEN 'Russian' THEN 'ru' WHEN 'Chinese' THEN 'zh' WHEN 'Japanese' THEN 'ja'
                       WHEN 'Korean' THEN 'ko' WHEN 'Arabic' THEN 'ar' WHEN 'Italian' THEN 'it' WHEN 'Turkish' THEN 'tr' WHEN 'Dutch' THEN 'nl'
                       WHEN 'Polish' THEN 'pl' WHEN 'Indonesian' THEN 'id' WHEN 'Vietnamese' THEN 'vi' WHEN 'Persian' THEN 'fa' WHEN 'Ukrainian' THEN 'uk'
                       WHEN 'Thai' THEN 'th' ELSE NULL END THEN 'Pedido no idioma do navegador'
                  WHEN u.idioma = 'English' THEN 'Inglês (navegador em outro idioma)'
                  ELSE 'Outro idioma (nem o do navegador, nem inglês)' END AS nivel
           FROM silver.fato_usuario u WHERE u.pais = 'Brazil' AND u.elegivel),
     s AS (SELECT nivel, count(*) AS elegiveis, count(*) FILTER (WHERE voltou_7d) AS voltaram FROM b WHERE nivel IS NOT NULL GROUP BY 1)
SELECT s.nivel, s.elegiveis, round(s.voltaram::numeric / s.elegiveis, 4) AS retorno,
       (s.elegiveis = g.elegiveis AND s.voltaram = g.voltaram_7d) AS bate_com_gold
FROM s JOIN gold.agg_retorno_fator g ON g.pais = 'Brazil' AND g.fator = 'idioma_x_navegador' AND g.nivel = s.nivel
ORDER BY s.elegiveis DESC;
```
**Passo a passo:** compara o código de idioma do navegador (ex.: `pt-BR` → `pt`) com o idioma detectado no pedido (ex.: `Portuguese` → `pt`). Iguais: "no idioma do navegador". Senão, se o pedido é em inglês: "inglês". Senão: "outro idioma".
**Deve dar:** no idioma do navegador: 1.560 · 0,2449; outro idioma: 343 · **0,1837**; inglês com navegador em outro idioma: 317 · 0,2587; todas `t`. É uma hipótese (a detecção de idioma erra).

---

# 4. Ajuda e a base de tudo

## 4.1 Problemas de qualidade dos dados
**Na tela:** a tabela "problemas encontrados" (conversas sem país, cópias exatas, hash repetido e outros).
> Esta é a única consulta em que **não** se troca o país (a tabela de problemas é da base inteira).

```sql
-- Refaz as contagens da tabela de problemas de qualidade a partir da bronze e da silver e compara com a gold.
-- Esta consulta é global: NÃO troque o país aqui. Quatro linhas (idioma, concentração, redigida e hora da mensagem) são sempre do Brasil, como na tela.
WITH s AS (SELECT * FROM (
  SELECT 'pais_vazio' AS codigo, count(*) FILTER (WHERE country IS NULL) AS afetadas, count(*) AS total FROM bronze.wildchat
  UNION ALL SELECT 'estado_vazio', count(*) FILTER (WHERE estado IS NULL), count(*) FROM silver.fato_conversa
  UNION ALL SELECT 'ua_vazio', count(*) FILTER (WHERE header->>'user-agent' IS NULL), count(*) FROM bronze.wildchat
  UNION ALL SELECT 'hash_repetido', count(*) FILTER (WHERE conversation_hash IN (SELECT conversation_hash FROM silver.fato_conversa GROUP BY 1 HAVING count(*) > 1)), count(*) FROM silver.fato_conversa
  UNION ALL SELECT 'duplicata_exata', (SELECT count(*) FROM bronze.wildchat) - (SELECT count(*) FROM silver.fato_conversa), (SELECT count(*) FROM bronze.wildchat)
  UNION ALL SELECT 'fuso', count(*), count(*) FROM silver.fato_conversa
  UNION ALL SELECT 'sem_texto', count(*) FILTER (WHERE conversation IS NULL), count(*) FROM bronze.wildchat
  UNION ALL SELECT 'msg_usuario_sem_horario', count(*) FILTER (WHERE conversation->0->>'timestamp' IS NULL), count(*) FROM bronze.wildchat WHERE conversation IS NOT NULL
  UNION ALL SELECT 'idioma_diferente', count(*) FILTER (WHERE idioma IS DISTINCT FROM 'Portuguese'), count(*) FROM silver.fato_conversa WHERE pais = 'Brazil'
  UNION ALL SELECT 'usuarios_concentrados', (SELECT sum(n) FROM (SELECT count(*) AS n FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY usuario_id ORDER BY 1 DESC LIMIT 10) x),
                                            (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')
  UNION ALL SELECT 'redigida', count(*) FILTER (WHERE redigida), count(*) FROM silver.fato_conversa WHERE pais = 'Brazil') q)
SELECT s.codigo, s.afetadas, s.total, (s.afetadas = g.afetadas AND s.total = g.total) AS bate_com_gold
FROM s JOIN gold.problema_qualidade g ON g.codigo = s.codigo
ORDER BY g.ordem;
```
**Passo a passo:** cada linha conta quantas conversas têm o problema (`afetadas`) em quantas (`total`). Os problemas de "país vazio", "navegador vazio", "duplicata" e "sem texto" são medidos na **bronze** (o dado como veio); os demais, na **silver**.
**Deve dar:** 11 linhas, todas `t`: país vazio 1.060 de 837.989; estado vazio 163.178 de 837.972; navegador vazio 24.192 de 837.989; hash repetido 13.201 de 837.972; cópia exata 17 de 837.989; sem texto 826.368 de 837.989; mensagem do usuário sem horário 11.621 de 11.621 (nenhuma, em nenhum país, tem horário); idioma diferente de português 2.824 de 11.621; redigida 56 de 11.621. As linhas `fuso` (837.972 conversas) e `usuarios_concentrados` (3.751 de 11.621) completam as 11.

## 4.2 Da bronze para a silver: nada sumiu sem registro
**Na tela:** base de todos os números.
```sql
-- Conversas do país na bronze, o que foi excluído (cópia exata, sem IP ou sem início) e o que ficou na silver.
SELECT (SELECT count(*) FROM bronze.wildchat WHERE coalesce(country, 'Desconhecido') = 'Brazil')    AS bronze,
       (SELECT count(*) FROM auditoria.registro_excluido e
         WHERE e.pais = 'Brazil'
           AND e.execucao_id = (SELECT max(id) FROM ops.etl_execucao WHERE status IN ('ok', 'alerta'))) AS excluidas,
       (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')                              AS silver;
```
**Passo a passo:** vale a regra **bronze = silver + excluídas**. Conversas sem país entram como "Desconhecido" na silver. A tabela `auditoria.registro_excluido` guarda cada linha excluída com o motivo.
**Deve dar:** 11.621 · 0 · 11.621 (Alemanha: 28.975 · 0 · 28.975). No total, 837.989 = 837.972 + 17.

---

## Conferir tudo de uma vez
O ETL já faz estas contas a cada carga (66 conferências em `ops.qa_resultado`) e o teste `docker compose --profile test run --rm testes-integracao` compara a API com a gold em 6 países. Os SQL deste documento servem para **você refazer à mão** qualquer número que a tela mostre.
Para ver o resultado das conferências da última carga:
```sql
SELECT transicao, verificacao, passou FROM ops.qa_resultado
WHERE execucao_id = (SELECT max(id) FROM ops.etl_execucao) ORDER BY passou, transicao;
```
