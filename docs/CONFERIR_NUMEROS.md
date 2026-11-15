# Conferir cada número do dashboard em SQL

Para cada número da tela há uma consulta que refaz a conta **a partir da silver** (pessoa por pessoa, conversa por conversa) e compara com o que a **gold** guarda, que é o que a tela mostra.
A coluna `bate_com_gold` deve vir **`t`** (verdadeiro). Se vier `f`, o número da tela não corresponde à silver.

**Como usar (DBeaver):** conexão `localhost:5433`, banco `retencao`, usuário `auditor`, senha `auditor` (somente leitura). Cole a consulta e execute.
**Para outro país:** troque `'Brazil'` pelo nome do país **em inglês**, como está na base (`'Germany'`, `'Portugal'`, `'United States'`). Em todas as consultas o país aparece **uma vez**, no `WHERE` ou no `JOIN` indicado.
Os valores abaixo são do Brasil; a Alemanha vem ao lado quando a diferença ajuda a entender (a tela dela mostra 18,9%).

> Como a tela fala "pessoa": é um **usuário** da silver (IP + família do navegador/sistema, sem versão), ver [`COMO_FUNCIONA.md`](COMO_FUNCIONA.md). **Elegível** é a pessoa cuja primeira vez tem a janela completa: 30 dias depois do início dos dados e 7 dias antes do fim.

| # | Número na tela | Onde aparece |
|---|---|---|
| 1 | Pessoas novas | Visão geral, cartão |
| 2 | Retorno em 7 dias e o intervalo | Visão geral, cartão principal |
| 3 | Conversas e conversas por pessoa | Visão geral, cartão |
| 4 | Recusa na primeira resposta | Visão geral, cartão |
| 5 | Voltou em 24 horas | Visão geral, cartão |
| 6 | Concentração (10 mais ativas) | Visão geral, cartão |
| 7 | Curva de retorno (24 h, 7 e 30 dias) | Visão geral e Coortes |
| 8 | Retorno por mês | Visão geral, gráfico de linha |
| 9 | Retorno por semana | Coortes, e a semana de 20/11/2023 do incidente |
| 10 | Retorno e recusa por versão do modelo | Visão geral, comparação de modelos |
| 11 | Uso por dia e hora (pico, expediente) | Visão geral, mapa de calor |
| 12 | GPT-4 por mês | Visão geral |
| 13 | Comparação entre países e média geral | Visão geral, barras |
| 14 | Retorno por tema do primeiro pedido | O que faz voltar |
| 15 | Da bronze para a silver (nada sumiu) | todas as telas |
| 16 | Efeitos: grupos, efeito bruto e o que é ajustado | O que faz voltar |

---

## 1. Pessoas novas
**Na tela:** "Pessoas novas" = 2.530 (Brasil).
```sql
-- Conta as pessoas da silver e compara com a soma das semanas da gold e com o total do país.
SELECT (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil')                  AS pessoas_silver,
       (SELECT sum(novos) FROM gold.agg_retorno_semana WHERE pais = 'Brazil')            AS pessoas_gold_semanas,
       (SELECT usuarios FROM gold.pais WHERE pais = 'Brazil')                            AS pessoas_gold_pais;
```
**O que faz:** `silver.fato_usuario` tem **uma linha por pessoa**, então `count(*)` é o número de pessoas. A gold guarda a mesma contagem de dois jeitos (por semana e por país); os três têm de ser iguais.
**Deve dar:** 2.530 · 2.530 · 2.530 (Alemanha: 4.544 nos três).

## 2. Retorno em 7 dias (o 23,7%)
**Na tela:** "23,7%", "530 de 2.234" e o intervalo "22,0% a 25,5%".
```sql
-- (a) A taxa: elegíveis, quantos voltaram em até 7 dias e a divisão. Compara com a gold.
WITH s AS (SELECT count(*) FILTER (WHERE elegivel)                    AS n,
                  count(*) FILTER (WHERE elegivel AND voltou_7d)      AS v
           FROM silver.fato_usuario WHERE pais = 'Brazil'),
     g AS (SELECT sum(elegiveis) AS n, sum(voltaram_7d) AS v
           FROM gold.agg_retorno_semana WHERE pais = 'Brazil')
SELECT s.n AS elegiveis, s.v AS voltaram, round(s.v::numeric / s.n, 4) AS retorno,
       (s.n = g.n AND s.v = g.v) AS bate_com_gold
FROM s, g;
```
**O que faz:** `elegivel` marca quem tem a janela completa e `voltou_7d` marca quem iniciou uma nova sessão em até 7 dias depois da primeira vez. A taxa é voltaram ÷ elegíveis. A parte `g` soma as semanas da gold (`agg_retorno_semana`), que é de onde a tela lê.
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
**O que faz:** aplica a fórmula do intervalo de Wilson (`z = 1,96`), a margem que diz "o valor verdadeiro provavelmente está entre estes dois números". Não depende de nenhuma função do banco.
**Deve dar:** 0,2201 e 0,2553, ou seja 22,0% a 25,5% (Alemanha: 0,1765 e 0,2012).

## 3. Conversas e conversas por pessoa
**Na tela:** "Conversas" = 11.621, "4,6 por pessoa".
```sql
-- Conta as conversas na silver, compara com a gold e divide pelas pessoas.
SELECT (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')   AS conversas_silver,
       (SELECT conversas FROM gold.pais WHERE pais = 'Brazil')             AS conversas_gold,
       round((SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')::numeric
           / (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil'), 1) AS conversas_por_pessoa;
```
**O que faz:** `silver.fato_conversa` tem **uma linha por conversa** (já sem as cópias exatas). A divisão pelo número de pessoas dá a média da tela.
**Deve dar:** 11.621 · 11.621 · 4,6 (Alemanha: 28.975 · 28.975 · 6,4).

## 4. Recusa na primeira resposta
**Na tela:** "8,9%", "198 de 2.234 pessoas". Em países sem texto a tela mostra "—".
```sql
-- Entre as pessoas elegíveis com texto, quantas receberam recusa ou desculpa já na primeira resposta.
WITH s AS (SELECT count(*) FILTER (WHERE recusa) AS com, count(*) AS total
           FROM silver.fato_usuario WHERE elegivel AND recusa IS NOT NULL AND pais = 'Brazil'),
     g AS (SELECT sum(elegiveis) FILTER (WHERE nivel = 'Com recusa') AS com, sum(elegiveis) AS total
           FROM gold.agg_retorno_fator WHERE pais = 'Brazil' AND fator = 'recusa')
SELECT s.com, s.total, round(s.com::numeric / nullif(s.total, 0), 4) AS taxa_recusa,
       (s.com = coalesce(g.com, 0) AND s.total = coalesce(g.total, 0)) AS bate_com_gold
FROM s, g;
```
**O que faz:** `recusa` é verdadeiro quando a abertura da primeira resposta casa os padrões de recusa/desculpa, falso quando não casa, e **vazio** quando o país não tem texto. O filtro `recusa IS NOT NULL` deixa de fora quem não tem texto.
**Deve dar:** 198 · 2.234 · 0,0886 · `t`. **Alemanha:** 0 · 0 · vazio · `t` (sem texto, o número não existe e a tela mostra "—").

## 5. Voltou em 24 horas
**Na tela:** "15,9%", "356 de 2.234".
```sql
-- Mesma base do retorno em 7 dias (elegíveis), mas contando quem voltou em até 24 horas.
WITH s AS (SELECT count(*) FILTER (WHERE elegivel)                  AS n,
                  count(*) FILTER (WHERE elegivel AND voltou_24h)   AS v
           FROM silver.fato_usuario WHERE pais = 'Brazil'),
     g AS (SELECT usuarios_elegiveis AS n, voltaram_24h AS v FROM gold.pais WHERE pais = 'Brazil')
SELECT s.n AS elegiveis, s.v AS voltaram_24h, round(s.v::numeric / s.n, 4) AS taxa,
       (s.n = g.n AND s.v = g.v) AS bate_com_gold
FROM s, g;
```
**O que faz:** igual à consulta 2, trocando `voltou_7d` por `voltou_24h` (nova sessão em até 24 h da primeira vez).
**Deve dar:** 2.234 · 356 · 0,1594 · `t` (Alemanha: 3.835 · 524 · 0,1366 · `t`).

## 6. Concentração do uso (10 pessoas mais ativas)
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
**O que faz:** `u` é "quantas conversas cada pessoa teve"; ordena da maior para a menor, pega as 10 primeiras e soma.
**Deve dar:** 3.751 · 11.621 · 0,3228 · `t` (Alemanha: 10.276 · 28.975 · 0,3547 · `t`).

## 7. Curva de retorno (24 horas, 7 dias, 30 dias)
**Na tela:** os pontos "16,0% em 1 dia, 24,0% em 7, 26,1% em 30".
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
**O que faz:** `dias_ate_voltar` é o tempo entre a primeira vez e o retorno. A consulta testa o mesmo prazo em três valores (`VALUES`) e conta quem voltou até lá.
**Deve dar:** 2.039 pessoas em todas as linhas; voltaram 326, 489 e 533; taxas 0,1599, 0,2398 e 0,2614; tudo `t`.
**Por que o 7 dias dá 24,0% e não 23,7%:** a curva usa só quem tem **30 dias** de janela completa (2.039 pessoas); o retorno em 7 dias usa a janela de **7 dias** (2.234). São bases diferentes, e isso está dito na tela.

## 8. Retorno por mês
**Na tela:** a linha mensal (mai./2023 = 22,3% … abr./2024 = 21,1%).
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
**O que faz:** `timezone(fuso, ...)` converte o horário de UTC para o fuso do país antes de achar o mês. A gold guarda esse retorno repartido por fator; somar o fator `modelo` reconstitui todas as pessoas elegíveis.
**Deve dar:** 12 meses, todos `t`. Mai./2023: 282 · 63 · 0,2234 e abr./2024: 185 · 39 · 0,2108.

## 9. Retorno por semana (a semana do incidente)
**Na tela:** Coortes semanais e o gráfico semanal. O PDF fala da semana de 20/11/2023.
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
**O que faz:** `semana` já vem calculada na silver (segunda-feira da semana da primeira vez). O `WHERE` final escolhe as semanas de 06/11 a 27/11/2023 (a do PDF é 20/11); troque as datas para ver outras.
**Deve dar (Brasil):** 06/11: 48 · 12 · 0,2500; 13/11: 55 · 16 · 0,2909; 20/11: 68 · 14 · 0,2059; 27/11: 67 · 14 · 0,2090; todas `t`. A Alemanha dá 105, 80, 132 e 108 pessoas nessas semanas.
Semanas com menos de 30 elegíveis aparecem na tela como "amostra pequena" e sem taxa; a conta aqui continua válida.
Os números do PDF (1.210 novos, 31% → 18%) são do exemplo do enunciado, não desta base: o que o incidente mostra é o **erro de código** que dobra os novos, explicado em [`INCIDENTE.md`](INCIDENTE.md).

## 10. Retorno e recusa por versão do modelo
**Na tela:** a comparação de modelos (barras por versão, cartões por família).
```sql
-- Por versão do modelo: o retorno em 7 dias (pessoas) e a recusa (conversas com texto).
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
**O que faz:** o retorno conta **pessoas** (pelo modelo da primeira conversa); a recusa conta **conversas** (de cada versão). São bases diferentes, por isso há duas partes (`u` e `c`) unidas pelo nome do modelo.
**Deve dar:** seis versões, todas `t`. Exemplos (Brasil): `gpt-3.5-turbo-0613`: 894 elegíveis, retorno 0,2304, recusa 0,0381; `gpt-4-1106-preview`: 433, 0,2794, 0,0760; `gpt-3.5-turbo-0301`: 343, 0,2391, recusa 0,1312.
Na Alemanha as seis versões também batem, mas a recusa fica vazia (0 conversas com texto).

## 11. Uso por dia e hora
**Na tela:** o mapa de calor, "pico às ...h" e "35,5% no expediente".
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
**O que faz:** `isodow` dá o dia da semana (1 = segunda … 7 = domingo). "Expediente" é segunda a sexta, das 9h às 17h59. `celulas_diferentes` conta as células (dia × hora) em que silver e gold discordam; tem de ser **0**.
**Deve dar:** 11.621 · 0,3555 · 11.621 · 0 (Alemanha: 28.975 · 0,3048 · 28.975 · 0).

## 12. GPT-4 por mês
**Na tela:** o gráfico "modelo no tempo" (GPT-4 era 15,7% em abr./2023, 0% em jul./2023).
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
**O que faz:** conta conversas por mês no fuso do país e separa as de GPT-4.
**Deve dar:** 13 meses, todos `t`. Abr./2023: 1.291 · 203 · 0,1572; mai./2023: 2.300 · 306 · 0,1330; jul. a out./2023: 0 de GPT-4; dez./2023: 678 · 513 · 0,7566; abr./2024: 713 · 661 · 0,9271.

## 13. Comparação entre países e média geral
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
**O que faz:** só países com 30 ou mais elegíveis aparecem na tela. A média geral soma voltaram e elegíveis de **todos** os países (cada pessoa com o mesmo peso).
**Deve dar:** 120 países · 0 divergentes · 0,2150. Esta consulta **não depende** de qual país está selecionado.

## 14. Retorno por tema do primeiro pedido
**Na tela:** "O que faz voltar", taxa por tema (ex.: Saudação = 14,8%). Só existe onde há texto (Brasil).
```sql
-- Retorno em 7 dias de cada tema do primeiro pedido, entre as pessoas elegíveis.
WITH s AS (SELECT t.tema AS nivel, count(*) AS elegiveis, count(*) FILTER (WHERE u.voltou_7d) AS voltaram
           FROM silver.fato_usuario u JOIN silver.dim_tema t ON t.tema_id = u.tema_id
           WHERE u.pais = 'Brazil' AND u.elegivel GROUP BY 1)
SELECT s.nivel AS tema, s.elegiveis, round(s.voltaram::numeric / s.elegiveis, 4) AS retorno,
       (s.elegiveis = g.elegiveis AND s.voltaram = g.voltaram_7d) AS bate_com_gold
FROM s JOIN gold.agg_retorno_fator g ON g.pais = 'Brazil' AND g.fator = 'tema' AND g.nivel = s.nivel
ORDER BY s.elegiveis DESC;
```
**O que faz:** `tema_id` liga a pessoa ao tema do primeiro pedido (`silver.dim_tema`). A mesma conta vale para os outros fatores (modelo, turnos, horário...), trocando `fator` e o `CASE` que define os níveis (ver `etl/camadas/gold/sql.py`).
**Deve dar:** `bate_com_gold = t` em todos os temas; Saudação: 386 elegíveis, 0,1477. Na **Alemanha** não volta nenhuma linha: não há texto, então não há tema.
**Atenção:** esta é a **taxa bruta**. O efeito mostrado na tela ("−8,1 pp", com intervalo) é **ajustado** por perfil (AIPW) e não sai de uma consulta simples; o método está em [`bdr/BDR-004-analise-de-efeitos.md`](bdr/BDR-004-analise-de-efeitos.md).

## 15. Da bronze para a silver: nada sumiu sem registro
**Na tela:** base de todos os números (Ajuda, "problemas de qualidade").
```sql
-- Conversas do país na bronze, o que foi excluído (cópia exata, sem IP ou sem início) e o que ficou na silver.
SELECT (SELECT count(*) FROM bronze.wildchat WHERE coalesce(country, 'Desconhecido') = 'Brazil')    AS bronze,
       (SELECT count(*) FROM auditoria.registro_excluido e
         WHERE e.pais = 'Brazil'
           AND e.execucao_id = (SELECT max(id) FROM ops.etl_execucao WHERE status IN ('ok', 'alerta'))) AS excluidas,
       (SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil')                              AS silver;
```
**O que faz:** vale a regra **bronze = silver + excluídas**. Conversas sem país entram como "Desconhecido" na silver. A tabela `auditoria.registro_excluido` guarda cada linha excluída com o motivo.
**Deve dar:** 11.621 · 0 · 11.621 (Alemanha: 28.975 · 0 · 28.975). No total, 837.989 = 837.972 + 17.

## 16. Efeitos na tela "O que faz voltar"
**O que dá e o que não dá para conferir em SQL.** Cada linha da tela tem duas partes:

| Parte | Em SQL? |
|---|---|
| Quantas pessoas em cada grupo (n), retorno do grupo de comparação, **efeito bruto** e o intervalo dele | **Sim**, consultas abaixo |
| **Efeito ajustado** (o número grande, ex.: +8,7), o intervalo dele, "grupos parecidos?", E-value | **Não**: é uma estimativa estatística (AIPW, regressão logística com validação cruzada) calculada em Python, em [`etl/camadas/gold/efeitos.py`](../etl/camadas/gold/efeitos.py). O SQL só lê o resultado guardado na gold. |

O efeito bruto é a diferença simples entre os dois grupos. O ajustado compara pessoas **parecidas** (mesmo mês, horário, sistema, navegador, estado, modelo, tema, tamanho do pedido, idioma), por isso é diferente do bruto (+8,7 contra +6,5 nos turnos). Método e limites em [`bdr/BDR-004-analise-de-efeitos.md`](bdr/BDR-004-analise-de-efeitos.md).

**(a) Efeito bruto de "2 ou mais turnos em vez de 1"** (a primeira linha da tela):
```sql
-- Divide as pessoas elegíveis em dois grupos (2+ turnos e 1 turno), calcula o retorno de cada um e a diferença em pontos percentuais.
WITH g AS (SELECT (turnos >= 2) AS tratado, count(*) AS n, avg(voltou_7d::int) AS p
           FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel GROUP BY 1),
     d AS (SELECT t.n AS n_tratados, c.n AS n_comparacao, round(c.p, 4) AS taxa_comparacao, 100 * (t.p - c.p) AS dif,
                  100 * 1.96 * sqrt(t.p*(1-t.p)/t.n + c.p*(1-c.p)/c.n) AS margem
           FROM g t, g c WHERE t.tratado AND NOT c.tratado)
SELECT d.n_tratados, d.n_comparacao, d.taxa_comparacao,
       round(d.dif, 2) AS bruto_pp, round(d.dif - d.margem, 2) AS bruto_ic_lo, round(d.dif + d.margem, 2) AS bruto_ic_hi,
       (d.n_tratados = e.n_tratados AND d.n_comparacao = e.n_controle AND round(d.dif, 2) = e.efeito_bruto_pp
        AND round(d.dif - d.margem, 2) = e.bruto_ic_lo AND round(d.dif + d.margem, 2) = e.bruto_ic_hi) AS bate_com_gold
FROM d, gold.efeito_fator e
WHERE e.pais = 'Brazil' AND e.fator = 'Turnos da primeira conversa';
```
**O que faz:** `g` calcula, para cada grupo, quantas pessoas há e a taxa de retorno. `d` subtrai as taxas e calcula a margem de erro de 95% (`1,96 × erro-padrão`). O final compara com a linha guardada em `gold.efeito_fator`.
**Deve dar:** 1.200 · 1.034 · 0,2021 · +6,54 [+3,04; +10,04] · `t`. É o "Efeito bruto +6,5 pp [+3,0; +10,0]" e o "retorno de 20,2%" da tela.

**(b) Efeito bruto de "Saudação em vez de Conhecimento/pergunta":**
```sql
-- Mesma conta, comparando só as pessoas cujo primeiro pedido foi uma saudação com as de uma pergunta de conhecimento.
WITH g AS (SELECT t.tema AS tema, count(*) AS n, avg(u.voltou_7d::int) AS p
           FROM silver.fato_usuario u JOIN silver.dim_tema t ON t.tema_id = u.tema_id
           WHERE u.pais = 'Brazil' AND u.elegivel AND t.tema IN ('Saudação', 'Conhecimento/pergunta') GROUP BY 1),
     d AS (SELECT t.n AS n_tratados, c.n AS n_comparacao, round(c.p, 4) AS taxa_comparacao, 100 * (t.p - c.p) AS dif,
                  100 * 1.96 * sqrt(t.p*(1-t.p)/t.n + c.p*(1-c.p)/c.n) AS margem
           FROM g t, g c WHERE t.tema = 'Saudação' AND c.tema = 'Conhecimento/pergunta')
SELECT d.n_tratados, d.n_comparacao, d.taxa_comparacao,
       round(d.dif, 2) AS bruto_pp, round(d.dif - d.margem, 2) AS bruto_ic_lo, round(d.dif + d.margem, 2) AS bruto_ic_hi,
       (d.n_tratados = e.n_tratados AND d.n_comparacao = e.n_controle AND round(d.dif, 2) = e.efeito_bruto_pp
        AND round(d.dif - d.margem, 2) = e.bruto_ic_lo AND round(d.dif + d.margem, 2) = e.bruto_ic_hi) AS bate_com_gold
FROM d, gold.efeito_fator e
WHERE e.pais = 'Brazil' AND e.fator = 'Tema do primeiro pedido' AND e.contraste = 'Saudação em vez de Conhecimento/pergunta';
```
**Deve dar:** 386 · 531 · 0,2561 · −10,85 [−15,97; −5,72] · `t`. A tela mostra n = 917 (386 + 531) e o efeito **ajustado** −8,1; o bruto (−10,9) é maior em módulo porque o ajuste desconta diferenças de perfil entre os grupos.

**Para os outros fatores**, troque só a definição do grupo `tratado`: recusa (`recusa` no lugar de `turnos >= 2`, com `AND recusa IS NOT NULL`) dá 198 · 2.036 · 0,2451 · −8,85 [−14,25; −3,46] · `t`; pedido longo (`prompt1_chars >= 60`, a mediana) dá 1.119 · 1.115 · 0,2000 · +7,44 [+3,92; +10,95] · `t`.

**(c) Ver exatamente o que a gold guardou (é isto que a tela mostra):**
```sql
-- Uma linha por efeito: grupos, efeito bruto, efeito ajustado com intervalo, sobreposição e E-value.
SELECT fator, contraste, n_tratados, n_controle, efeito_bruto_pp, efeito_pp AS efeito_ajustado_pp, ic_lo, ic_hi,
       sobreposicao AS grupos_parecidos_pct, e_value, ajustado_por
FROM gold.efeito_fator
WHERE pais = 'Brazil'
ORDER BY abs(efeito_pp) DESC;
```
**O que faz:** só lê a tabela. Para turnos: ajustado 8,72 [3,3; 14,14], sobreposição 97,9% ("97,9% das pessoas têm chance comparável"), E-value 2,26.
**Como confiar no ajustado, se não sai de SQL:** (1) o código é o `efeitos.py`, com semente fixa e ordem fixa das linhas, então a mesma base dá sempre o mesmo número (a conferência de **deriva** da carga acusa se mudar); (2) o bruto acima mostra que a base do cálculo (grupos e retornos) está certa; (3) a sensibilidade e os limites estão em `docs/SENSIBILIDADE.md` e no BDR-004. **Ele mostra associação ajustada, não prova de causa.**

---

## Conferir tudo de uma vez
O ETL já faz estas contas a cada carga (66 conferências em `ops.qa_resultado`) e o teste `docker compose --profile test run --rm testes-integracao` compara a API com a gold em 6 países. Os SQL deste documento servem para **você refazer à mão** qualquer número que a tela mostre.
Para ver o resultado das conferências da última carga:
```sql
SELECT transicao, verificacao, passou FROM ops.qa_resultado
WHERE execucao_id = (SELECT max(id) FROM ops.etl_execucao) ORDER BY passou, transicao;
```
