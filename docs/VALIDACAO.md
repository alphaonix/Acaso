# Validação conjunta (você confere, eu calculo)

Regra: nenhum número vai para a entrega sem ter sido recalculado por um segundo caminho.
Preencha a coluna "Bateu?" e anote divergências no log no fim. Isso alimenta o parágrafo de uso de IA do documento.

## Rodada 1: base e definição principal (use os CSVs em exports/ no Power BI)

| # | O que conferir | Como conferir no Power BI | Esperado | Bateu? |
|---|---|---|---|---|
| 1 | Total de conversas | contagem de linhas de `conversas_brasil` | 11.621 | |
| 2 | IPs distintos | contagem distinta de `ip_id` | 2.385 | |
| 3 | Período | mín. e máx. de `inicio_local` | 08/04/2023 a 29/04/2024 (fim = último fim_local) | |
| 4 | Conversas por modelo | contagem por `model` | gpt-3.5-turbo-0301: 3.971; 0613: 3.593; gpt-4-1106-preview: 1.882; 4-0125-preview: 1.334; gpt-4-0314: 684; 3.5-0125: 157 | |
| 5 | Idioma | contagem por `language` | Portuguese 8.797; English 1.868; Spanish 158 | |
| 6 | Conversas de 1 turno | % com `turn = 1` | ~56,2% | |
| 7 | Redigidas | soma de `redacted` | 56 | |
| 8 | Usuários | contagem de linhas de `usuarios_brasil` | 2.530 | |
| 9 | Usuários elegíveis | soma de `elegivel` | 2.234 | |
| 10 | Retorno em 7 dias | média de `voltou_7d` com `elegivel = 1` | 23,7% | |
| 11 | Conversas por usuário | some `convs_total` por usuário e compare com a contagem de `conversas_brasil` por `usuario_id` | iguais | |
| 12 | Concentração | maior `ip_id` por contagem de conversas | 1 IP com 1.557 | |
| 13 | Navegadores por IP | para cada `ip_id`, contagem distinta de `ua_norm`; % de IPs com mais de 1 | calcular e anotar (ref.: 11,3% com mais de 1 user-agent bruto) | |
| 14 | Qualidade da normalização | contagem de conversas por `ua_norm` | `Outro/Outro` pequeno; se grande, as regras de texto falham | |
| 15 | Ligação usuário-conversa | contagem distinta de `usuario_id` em `conversas_brasil` | 2.530 | |

### Itens adicionados após a conferência no Power BI (primeira experiência)
| # | O que conferir | Como conferir | Esperado | Bateu? |
|---|---|---|---|---|
| 16 | Conversas com recusa | soma de `recusa` em `conversas_brasil` | 911 (7,8% das 11.621) | Sim |
| 17 | Usuários com recusa na 1ª conversa | soma de `recusa` em `usuarios_brasil` | 230 (9,1% de 2.530) | |
| 18 | Redigidas | contar linhas com `redacted = TRUE` (a "Contagem" simples dá 11.621, errado) | 56 | |
| 19 | Tamanho do 1º pedido | MÉDIA (não soma) de `prompt1_chars` em `conversas_brasil` | ~904 caracteres | |

**Lição:** todo número tem UNIDADE (conversa ou usuário) e DENOMINADOR. 911 e 230 são ambos "recusa", mas contam coisas
diferentes. "Contagem" de coluna booleana conta linhas, não verdadeiros. Soma de tamanho não é métrica; usar média/mediana.
Por isso cada indicador do dashboard declara unidade, fórmula e denominador (ver BDR-002).

## Rodada 4: conferir a carga no DBeaver (conexão `localhost:5433`, banco `retencao`, usuário `etl`)
O ETL já confere sozinho 14 itens (`ops.qa_resultado`), mas a validação independente é sua. Rode cada consulta e compare:

| # | Consulta | Esperado |
|---|---|---|
| 20 | `SELECT count(*) FROM silver.fato_conversa WHERE pais = 'Brazil';` | 11.621 |
| 21 | `SELECT count(*), count(*) FILTER (WHERE elegivel) FROM silver.fato_usuario WHERE pais = 'Brazil';` | 2.530 e 2.234 |
| 22 | `SELECT round(avg(voltou_7d::int) FILTER (WHERE elegivel), 4) FROM silver.fato_usuario WHERE pais = 'Brazil';` | 0,2372 |
| 23 | `SELECT estado, count(DISTINCT usuario_id) FROM silver.fato_conversa WHERE pais='Brazil' GROUP BY 1 ORDER BY 2 DESC LIMIT 3;` | São Paulo 848, Rio de Janeiro 278, Minas Gerais 251 |
| 24 | `SELECT verificacao, esperado, obtido, passou FROM ops.qa_resultado ORDER BY id;` | 14 linhas, todas `passou = true` |
| 25 | `SELECT count(*) FROM silver.fato_conversa;` | 837.972 (837.989 lidas menos 17 repetições exatas) |
| 26 | `SELECT sum(linhas) FROM ops.bronze_lote;` | 837.989 |
| 27 | `SELECT semana, novos, elegiveis, voltaram_7d, round(taxa*100,1), round(ic_lo*100,1), round(ic_hi*100,1) FROM gold.agg_retorno_semana WHERE pais='Brazil' ORDER BY semana;` | confira que `taxa` vem vazia onde `elegiveis` < 30 |

Item 27: o intervalo de confiança semanal é largo (cerca de 85 usuários novos por semana no Brasil): isso é achado, não erro.

## Rodada 5: efeitos brutos no DBeaver (o AIPW não se recalcula em SQL, mas o efeito BRUTO sim)
Esta rodada confere a base do efeito: as taxas de cada grupo, só entre elegíveis do Brasil. Compare a diferença com a coluna "Bruto".
```sql
-- Recusa (esperado: com recusa 198 usuários, ~15,7%; sem recusa ~24,5%; diferença ~ -8,9 pp)
SELECT recusa, count(*) AS n, round(100*avg(voltou_7d::int),2) AS retorno_pct
FROM silver.fato_usuario WHERE pais='Brazil' AND elegivel GROUP BY 1;
-- Modelo (esperado: GPT-4 956 usuários ~24,2%; GPT-3.5 1.278 ~23,4%; diferença ~ +0,8 pp)
SELECT (modelo LIKE 'gpt-4%') AS gpt4, count(*) AS n, round(100*avg(voltou_7d::int),2) AS retorno_pct
FROM silver.fato_usuario WHERE pais='Brazil' AND elegivel GROUP BY 1;
-- Turnos (esperado: 2+ turnos 1.200 usuários ~26,7%; 1 turno 1.034 ~20,2%; diferença ~ +6,5 pp)
SELECT (turnos >= 2) AS dois_ou_mais, count(*) AS n, round(100*avg(voltou_7d::int),2) AS retorno_pct
FROM silver.fato_usuario WHERE pais='Brazil' AND elegivel GROUP BY 1;
-- Efeitos gravados pelo ETL, ordenados pelo tamanho
SELECT fator, contraste, efeito_bruto_pp, efeito_pp, ic_lo, ic_hi, e_value_ic FROM gold.efeito_fator ORDER BY abs(efeito_pp) DESC;
```
Perguntas de bom senso: o efeito de GPT-4 ser ~0 faz sentido para você? A recusa tem mesmo ~200 usuários? Conferiu a amostra de recusa (`amostra_validacao_recusa.csv`)? Se o detector erra muito, o efeito de recusa não vale.

## Rodada 6: da bronze para a silver, no DBeaver (o bruto agora é consultável)
A bronze é uma tabela com o dado bruto (`bronze.wildchat`; as linhas do Brasil têm o TEXTO das conversas: uso local, não compartilhe).
```sql
-- 1. A bronze tem todas as linhas dos arquivos (esperado: Brasil 11.621 linhas com 11.621 com_texto; outros países 826.368 com 0)
SELECT arquivo_origem, count(*) AS linhas, count(conversation) AS com_texto FROM bronze.wildchat GROUP BY 1;
-- 2. Ver o bruto: uma linha por conversa; a lista de mensagens fica em `conversation` (JSON)
SELECT conversation_hash, model, turn, country, state, header->>'user-agent' AS user_agent, "timestamp",
       conversation->1->>'timestamp' AS ts_resposta, left(conversation->0->>'content', 60) AS inicio_do_pedido
FROM bronze.wildchat WHERE country = 'Brazil' LIMIT 20;
-- 3. Mensagens do USUARIO não têm horário (esperado 0): por isso o início da conversa é a 1ª resposta do assistente
SELECT count(*) AS linhas_com_texto,
       count(*) FILTER (WHERE conversation->0->>'timestamp' IS NOT NULL) AS msg1_usuario_com_horario,   -- esperado 0
       count(*) FILTER (WHERE conversation->1->>'timestamp' IS NOT NULL) AS msg2_assistente_com_horario, -- esperado 11.621
       count(*) FILTER (WHERE conversation->0->>'role' = 'user')      AS msg1_e_usuario,                 -- esperado 11.621
       count(*) FILTER (WHERE conversation->1->>'role' = 'assistant') AS msg2_e_assistente               -- esperado 11.621
FROM bronze.wildchat WHERE conversation IS NOT NULL;
-- 3b. O início é primeira_resposta_ts em todos os países (esperado: 837.989 linhas, 837.989 preenchidas, 0 vazias; e no Brasil ela é igual ao horário da mensagem 2: 11.621)
SELECT count(*) AS linhas, count(primeira_resposta_ts) AS preenchidas, count(*) - count(primeira_resposta_ts) AS vazias,
       count(*) FILTER (WHERE conversation IS NOT NULL AND primeira_resposta_ts = (conversation->1->>'timestamp')::timestamptz) AS brasil_igual_a_mensagem_2
FROM bronze.wildchat;
-- 4. Do bruto para a silver, para um hash (cole um da consulta 2; hash repetido gera mais de uma linha, e é normal)
SELECT b.conversation_hash, b.state, b.turn, s.usuario_id, s.inicio_utc, s.duracao_s, t.tema, s.recusa
FROM bronze.wildchat b
JOIN silver.fato_conversa s ON s.conversation_hash = b.conversation_hash AND s.pais = 'Brazil'
LEFT JOIN silver.dim_tema t USING (tema_id)
WHERE b.conversation_hash = '<cole um hash aqui>';
-- 5. Linhagem: cada lote aponta para a tabela onde foi carregado (esperado: 2 linhas, tabela_destino preenchida)
SELECT arquivo, linhas, tabela_destino, left(sha256, 12) AS sha FROM ops.bronze_lote ORDER BY id DESC LIMIT 2;
-- 6. Os países fora do Brasil: 1.060 linhas sem país na bronze (viram "Desconhecido" na silver)
SELECT count(*) FROM bronze.wildchat WHERE country IS NULL;
```
Perguntas de bom senso: a consulta 4 mostra o que a silver guardou e o que descartou (o texto)? O tema que apareceu faz sentido
para o início do pedido que você viu na consulta 2?

## Rodada 7: auditoria entre camadas no DBeaver (schema `auditoria`; é o que o ETL registra a cada carga)
O schema `auditoria` guarda **só a última carga** (o histórico das cargas está em `ops.etl_execucao`). As três camadas são
contadas **na mesma unidade (conversas)**, então se comparam: a diferença entre uma e outra são só as excluídas.
```sql
-- 0. COMECE POR AQUI (visão auditoria.camadas; esperado em '(todos)': bronze 837.989 | silver 837.972 (17 excluídas, todas duplicata_exata) | gold 837.972; 'confere' = true nas três)
SELECT ordem, camada, linhas, excluidas, excl_sem_inicio, excl_sem_ip, excl_duplicadas, esperado, confere
FROM auditoria.camadas WHERE pais = '(todos)' ORDER BY ordem;
-- o mesmo para o Brasil (esperado: 11.621 nas três, 0 excluídas)
SELECT ordem, camada, linhas, excluidas, esperado, confere FROM auditoria.camadas WHERE pais = 'Brazil' ORDER BY ordem;
```
As demais consultas abaixo continuam válidas (o filtro por última carga é redundante, mas inofensivo).
```sql
-- 1. (removida: a contagem por tabela foi substituída pela visão auditoria.camadas, acima)
-- 2. Conservação: bronze = silver + excluídas (esperado: 837.989 = 837.972 + 17)
SELECT (SELECT count(*) FROM bronze.wildchat) AS bronze, (SELECT count(*) FROM silver.fato_conversa) AS silver,
       (SELECT count(*) FROM auditoria.registro_excluido WHERE execucao_id = (SELECT max(execucao_id) FROM auditoria.fluxo_pais)) AS excluidas;
-- 3. O funil por país (esperado Brasil: 11.621 -> 0 excluídas -> 11.621 conversas -> 2.530 usuários -> 2.530 na gold; '(todos)': 837.989 / 17 / 837.972 / 197.319)
SELECT pais, bronze_linhas, excl_duplicadas, silver_conversas, silver_usuarios, gold_usuarios, pais_tratado
FROM auditoria.fluxo_pais WHERE execucao_id = (SELECT max(execucao_id) FROM auditoria.fluxo_pais) AND pais IN ('Brazil', '(todos)', 'Desconhecido');
-- 4. As linhas excluídas (esperado: 17, todas 'duplicata_exata', em 4 países)
SELECT bronze_id, pais, motivo, mantida_bronze_id FROM auditoria.registro_excluido
WHERE execucao_id = (SELECT max(execucao_id) FROM auditoria.fluxo_pais) ORDER BY bronze_id;
-- 5. Cada excluída é MESMO uma cópia exata da que ficou? (esperado: 17 linhas, todas true)
SELECT e.bronze_id AS excluida, e.mantida_bronze_id AS mantida, a.conversation_hash = b.conversation_hash AS mesmo_hash,
       a.hashed_ip = b.hashed_ip AS mesmo_ip, a.primeira_resposta_ts = b.primeira_resposta_ts AS mesmo_inicio
FROM auditoria.registro_excluido e
JOIN bronze.wildchat a ON a.bronze_id = e.bronze_id JOIN bronze.wildchat b ON b.bronze_id = e.mantida_bronze_id
WHERE e.execucao_id = (SELECT max(execucao_id) FROM auditoria.fluxo_pais);
-- 6. Nulos antes e depois (esperado: pais 1.060 -> 0 'preenchido'; estado 163.179 -> 163.178; texto 826.368 -> 826.351; msg_usuario_horario 11.621 de 11.621)
SELECT codigo, linhas_bronze, nulos_bronze, linhas_silver, nulos_silver, acao FROM auditoria.nulos
WHERE execucao_id = (SELECT max(execucao_id) FROM auditoria.fluxo_pais) ORDER BY ordem;
-- 7. Antes e depois (esperado: 20 linhas, 4 tratamentos x 5 exemplos)
SELECT tratamento, antes, depois FROM auditoria.antes_depois
WHERE execucao_id = (SELECT max(execucao_id) FROM auditoria.fluxo_pais) ORDER BY tratamento, ordem;
-- 8. Conferências por transição entre camadas (esperado: bronze_arquivos 5, bronze_silver 3, silver_interna 7, silver_gold 8, efeitos 3, validados 10; todas passaram)
SELECT transicao, count(*) AS total, count(*) FILTER (WHERE passou) AS passaram FROM ops.qa_resultado
WHERE execucao_id = (SELECT max(execucao_id) FROM auditoria.fluxo_pais) GROUP BY 1 ORDER BY 1;
```
Perguntas de bom senso: a diferença de 1 nos nulos de `estado` e a de 17 nos de `texto` são as duplicatas excluídas? (sim: uma das 17
tinha estado vazio, e todas são de fora do Brasil). Os nulos de `texto` fora do Brasil (826.351) são esperados por desenho?

## Rodada 2: verificação manual de um usuário (a mais importante)

1. Em `usuarios_brasil`, escolha um usuário com `elegivel = 1`, `voltou_7d = 1` e `convs_total` entre 3 e 6.
2. Em `conversas_brasil`, filtre pelo `usuario_id` e ordene por `inicio_local`.
3. Calcule à mão: houve nova sessão (intervalo maior que 30 min após o `fim_local` da anterior) começando em até
   7 dias após a primeira? Se sim, `voltou_7d` deve ser 1.
4. Repita com um usuário `voltou_7d = 0` e com um de uma única conversa. Três casos bastam.

## Perguntas de bom senso (anote a resposta, não precisa de número)
- A taxa de retorno por semana varia de forma plausível ou há semanas absurdas (0% ou 100%)? Se sim, olhe o `n` da semana.
- O pico de abr/mai de 2023 é muita gente nova ou poucos IPs fazendo muito volume?
- Os 56% de conversas de 1 turno fazem sentido para um assistente gratuito?

## Log de divergências e correções
| Data | Item | O que eu calculei | O que você achou | Causa | Resolução |
|---|---|---|---|---|---|
| | | | | | |


## Rodada 8: cartões novos da Visão geral (conferir no DBeaver; valores do Brasil)
Os seis cartões vêm de `gold.pais` e `gold.agg_*`. Os três novos ainda **não** estão no portão de qualidade; confira e me diga se batem.
```sql
-- Conversas (esperado 11.621) e por usuário (esperado 4,6 = 11.621 / 2.530)
SELECT count(*) AS conversas, round(count(*)::numeric / (SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil'), 1) AS por_usuario
FROM silver.fato_conversa WHERE pais = 'Brazil';
-- Turnos da 1ª conversa: média (esperado 2,5) e mediana (esperado 2)
SELECT round(avg(turnos), 2) AS media, percentile_cont(0.5) WITHIN GROUP (ORDER BY turnos) AS mediana
FROM silver.fato_usuario WHERE pais = 'Brazil';
-- Uso de GPT-4 entre os usuários, 1ª conversa (esperado 44,8%; entre os elegíveis, que alimentam a rosca, 42,8%)
SELECT round(100 * avg((modelo LIKE 'gpt-4%')::int), 1) AS pct_gpt4_todos,
       round(100 * avg((modelo LIKE 'gpt-4%')::int) FILTER (WHERE elegivel), 1) AS pct_gpt4_elegiveis
FROM silver.fato_usuario WHERE pais = 'Brazil';
```

## Rodada 9: métricas ampliadas (Coortes, O que faz voltar e Explorar; conferir no DBeaver; valores do Brasil)
Vêm de `silver.fato_usuario` e `silver.fato_conversa`; a gold só agrupa. **Ainda não estão no portão de qualidade** (os números validados só entram lá depois de você conferir). As consistências entre camadas (somas, curva que não decresce, 24 h ⊂ 7 dias) já rodam a cada carga.
```sql
-- 9.1 Curva de retorno: base com 30 dias de janela completa (esperado 2.039), voltou em 24 h (326 = 16,0%), 7 dias (489 = 24,0%), 30 dias (533 = 26,1%)
SELECT count(*) FILTER (WHERE janela_30d) AS base,
       count(*) FILTER (WHERE janela_30d AND voltou_24h) AS em_24h,
       count(*) FILTER (WHERE janela_30d AND dias_ate_voltar <= 7) AS em_7d,
       count(*) FILTER (WHERE janela_30d AND dias_ate_voltar <= 30) AS em_30d,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY dias_ate_voltar) FILTER (WHERE janela_30d AND dias_ate_voltar <= 30))::numeric, 2) AS mediana_dias   -- esperado 0,63
FROM silver.fato_usuario WHERE pais = 'Brazil';

-- 9.2 Concentração: pessoas por faixa de conversas (esperado 1: 1.516 · 2-3: 556 · 4-10: 308 · 11+: 150) e conversas (1.516 · 1.285 · 1.796 · 7.024)
WITH u AS (SELECT usuario_id, count(*) AS n FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY 1)
SELECT CASE WHEN n = 1 THEN '1' WHEN n <= 3 THEN '2-3' WHEN n <= 10 THEN '4-10' ELSE '11+' END AS faixa, count(*) AS pessoas, sum(n) AS conversas
FROM u GROUP BY 1 ORDER BY min(n);
-- 10 mais ativas: esperado 3.751 conversas de 11.621 (32,3%); a mais ativa: 1.556 (13,4%)
WITH u AS (SELECT usuario_id, count(*) AS n FROM silver.fato_conversa WHERE pais = 'Brazil' GROUP BY 1)
SELECT (SELECT sum(n) FROM (SELECT n FROM u ORDER BY n DESC LIMIT 10) x) AS top10, (SELECT max(n) FROM u) AS maior, (SELECT sum(n) FROM u) AS total;

-- 9.3 Quando usam (fuso de São Paulo): expediente seg-sex 9h-18h (esperado 35,5%) e madrugada 22h-6h (esperado 20,1%)
SELECT round(100 * avg((extract(isodow FROM inicio_utc AT TIME ZONE 'America/Sao_Paulo') <= 5
                        AND extract(hour FROM inicio_utc AT TIME ZONE 'America/Sao_Paulo') BETWEEN 9 AND 17)::int), 1) AS expediente,
       round(100 * avg((extract(hour FROM inicio_utc AT TIME ZONE 'America/Sao_Paulo') >= 22
                        OR extract(hour FROM inicio_utc AT TIME ZONE 'America/Sao_Paulo') < 6)::int), 1) AS madrugada
FROM silver.fato_conversa WHERE pais = 'Brazil';

-- 9.4 Recusa por versão do modelo (esperado: 3.5-0301 521/3.971 = 13,1% · 3.5-0613 137/3.593 = 3,8% · 3.5-0125 4/157 = 2,5% · gpt-4-0314 43/684 = 6,3% · gpt-4-1106 143/1.882 = 7,6% · gpt-4-0125 63/1.334 = 4,7%)
SELECT modelo, count(*) AS conversas, count(*) FILTER (WHERE recusa) AS com_recusa, round(100 * avg(recusa::int), 1) AS pct
FROM silver.fato_conversa WHERE pais = 'Brazil' AND recusa IS NOT NULL GROUP BY 1 ORDER BY 1;

-- 9.5 Saudação e recusa dentro de cada modelo, só elegíveis (esperado: saudação 3.5 = 237 (36 voltam) · 4 = 149 (21); recusa 3.5 = 110 (21) · 4 = 88 (10))
SELECT CASE WHEN u.modelo LIKE 'gpt-4%' THEN 'GPT-4' ELSE 'GPT-3.5' END AS familia,
       count(*) FILTER (WHERE t.tema = 'Saudação') AS saudacao, count(*) FILTER (WHERE t.tema = 'Saudação' AND u.voltou_7d) AS saudacao_voltou,
       count(*) FILTER (WHERE u.recusa) AS recusa, count(*) FILTER (WHERE u.recusa AND u.voltou_7d) AS recusa_voltou
FROM silver.fato_usuario u LEFT JOIN silver.dim_tema t USING (tema_id) WHERE u.pais = 'Brazil' AND u.elegivel GROUP BY 1;

-- 9.6 Dispositivo, só elegíveis (esperado: celular 734, 176 voltam · computador 1.500, 354 voltam)
SELECT sistema IN ('Android', 'iOS') AS celular, count(*) AS elegiveis, count(*) FILTER (WHERE voltou_7d) AS voltaram
FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel GROUP BY 1;

-- 9.7 Idioma do pedido × do navegador: pessoas elegíveis com os dois idiomas conhecidos (esperado 2.220 = 1.560 + 343 + 317; sem um deles: 14)
SELECT count(*) FILTER (WHERE idioma_navegador <> '' AND idioma IS NOT NULL) AS com_os_dois,
       count(*) FILTER (WHERE idioma_navegador = '' OR idioma IS NULL) AS sem
FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel;
```