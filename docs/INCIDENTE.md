# Investigação do incidente: "o retorno caiu de 31% para 18%" (PDF, seção 4.2)

**Resposta em uma frase:** o retorno não caiu. O endpoint calcula "pessoa" como `hash(hashed_ip + user-agent bruto)` e, na semana de
20/11, cerca de 860 pessoas já conhecidas passaram a contar como "novas" (o user-agent delas mudou); os "voltaram" ficaram parados
(375, 368, 366) e os "novos" quase dobraram (1.210, 1.188, **2.034**), o que derruba a divisão de 31% para 18%. O defeito está na **carga**
(como o `usuario_id` é calculado) e aparece na base analítica; o gatilho exato daquela semana se confirma com as consultas abaixo.

## 1. Por onde eu começaria e por quê
**Pelo número, não pelo código.** Retorno é `voltaram ÷ novos`; olho cada parte separada, com o que já tenho em mãos:

| Semana | Dashboard: novos | voltaram | Relatório (base bruta): novos | voltaram |
|---|---:|---:|---:|---:|
| 06/11 | 1.210 | 375 | 1.150 | 345 |
| 13/11 | 1.188 | 368 | 1.131 | 351 |
| 20/11 | **2.034** | 366 | 1.172 | 352 |

- Os **voltaram não mudam** (375 → 368 → 366). A queda inteira vem do **denominador** (novos): +862 pessoas "novas" só na semana de 20/11.
- O relatório do time de dados (que conta por `hashed_ip`) fica estável em ~30%. Então são **duas definições de "pessoa"** que divergem, e a divergência
  explode numa semana só.
- Mesmo nas semanas boas o dashboard conta ~5% a mais (1.210 contra 1.150; 1.188 contra 1.131): é um **defeito estrutural** que a semana de 20/11 amplificou.

Por que começar assim: é barato, já localiza a **camada** antes de abrir código e evita a reação errada (culpar o produto, reprocessar tudo ou
"corrigir" o gráfico). E, em paralelo, aviso a gerente de que o 18% não é confiável (ver item 5).

## 2. Em qual camada está a falha, e as evidências
**Carga, com efeito na base analítica.** Eliminando as outras:
- **Tela:** não. A resposta do endpoint (monitoramento, `req_4c19a2`) já traz 2.034; a tela só desenha o que a API devolve.
- **Backend:** não é a causa principal. A consulta soma o que a base tem; um número errado de "novos" já está nas linhas que ela lê.
- **Base bruta:** não. O relatório do time lê a bruta e dá estável.
- **Carga:** `usuario_id = sha256(hashed_ip + "|" + header["user-agent"])`. O user-agent **bruto** muda com a versão do navegador, do
  aplicativo ou por um proxy. Quando muda, a mesma pessoa vira outro `usuario_id` e aparece como "nova". O relatório usa só `hashed_ip`, que não muda.
- **Defeitos secundários, também no código** (explicam a divergência de ~5% nas semanas normais e fragilizam o indicador):
  `primeira_vez = min(ultimo_turno)` usa o **fim** da conversa (e não o início) e em UTC (`date_trunc('week')` conta a semana de Greenwich, não a de São Paulo);
  a regra "voltou = qualquer conversa **mais de 1 hora** depois" não é uma sessão; `ON CONFLICT DO NOTHING` guarda a primeira versão de uma conversa que
  continua nos dias seguintes (o `ultimo_turno` fica desatualizado); e não há elegibilidade (coorte com janela de 7 dias ainda aberta entra no cálculo).

**Hipótese de gatilho.** Algo mudou o user-agent de muita gente na semana de 20/11: atualização de navegador em massa, tráfego automatizado, ou um
proxy/CDN que reescreveu o cabeçalho. Como quase ninguém desses "novos" volta em 7 dias, parecem identidades que surgem uma vez. O **defeito é certo**
(qualquer mudança de user-agent o dispara); **qual foi o gatilho** se confirma com os dados, não com o raciocínio.

**Consulta de confirmação** (na base **bruta**, porque a base analítica não guarda IP nem user-agent):
```sql
-- Quantas "pessoas novas" por semana são, na verdade, um IP que já existia com outro user-agent?
WITH par AS (
  SELECT hashed_ip, header->>'user-agent' AS ua, min(primeira_resposta_ts) AS primeira_par
  FROM bronze.wildchat
  WHERE country = 'Brazil' AND hashed_ip IS NOT NULL AND primeira_resposta_ts IS NOT NULL
  GROUP BY 1, 2),
ip AS (SELECT hashed_ip, min(primeira_par) AS primeira_ip FROM par GROUP BY 1)
SELECT date_trunc('week', timezone('America/Sao_Paulo', p.primeira_par))::date AS semana,
       count(*)                                                AS novos_por_ip_e_ua,   -- o que o dashboard conta
       count(*) FILTER (WHERE p.primeira_par = i.primeira_ip)  AS novos_por_ip,        -- o que o relatório conta
       count(*) FILTER (WHERE p.primeira_par > i.primeira_ip)  AS ids_fantasma         -- IP já conhecido contado como novo
FROM par p JOIN ip i USING (hashed_ip)
GROUP BY 1 ORDER BY 1;
```
- **Se a hipótese estiver certa:** `novos_por_ip` bate com o relatório (1.150 / 1.131 / 1.172) e `ids_fantasma` é ~60 nas semanas normais e **~860 em 20/11**.
- **Segunda consulta, para achar o gatilho:** os user-agents mais comuns entre os fantasmas daquela semana.
  Um ou poucos valores novos concentrando quase tudo indicam uma atualização de versão ou um proxy; muitos valores diferentes, tráfego automatizado.
```sql
SELECT p.ua, count(*) AS ids_fantasma
FROM par p JOIN ip i USING (hashed_ip)
WHERE p.primeira_par > i.primeira_ip
  AND date_trunc('week', timezone('America/Sao_Paulo', p.primeira_par)) = timestamp '2023-11-20'
GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
```
- **Se `ids_fantasma` não explicar:** passo para as hipóteses seguintes, nesta ordem: carga duplicada (`SELECT conversa_id, count(*)` por dia na bruta contra a analítica) e
  regra de "primeira vez" em UTC (conversas perto da meia-noite de domingo).

**O mecanismo existe nos dados reais.** Na base do Brasil (nossa): 2.385 IPs geram **2.895** pares IP + user-agent (+21%); 269 IPs usam mais de um user-agent (um deles, 35);
e 510 pares parecem "novos" num IP que já existia. A mesma consulta acima, rodada na nossa base, mostra 15 a 17 "ids fantasma" por semana nas semanas mais afetadas
(em 37 a 100 novos), ou seja, a fragmentação é real e grande, mesmo sem um gatilho específico.

## 3. O trecho de código que causa o problema, e a correção
**Causa (carga):** `chave = f"{c['hashed_ip']}|{c['header']['user-agent']}"` e `ultimo_turno = c["timestamp"]`. **Correção:**
```python
import re
from hashlib import sha256

def familia_navegador(ua: str | None) -> str:
    """'Chrome/Windows': família do navegador + sistema, SEM o número de versão (BDR-001)."""
    ua = ua or ""
    nav = ("Edge" if "Edg/" in ua else "Opera" if "OPR/" in ua else "Firefox" if "Firefox" in ua
           else "Chrome" if "Chrome" in ua else "Safari" if "Safari" in ua else "Outro")
    so = ("Android" if "Android" in ua else "iOS" if re.search("iPhone|iPad", ua) else "Windows" if "Windows" in ua
          else "Mac" if "Mac OS" in ua else "Linux" if "Linux" in ua else "Outro")
    return f"{nav}/{so}"

def carregar_conversas(conversas: list[dict]) -> None:
    for c in conversas:
        usuario_id = sha256(f"{c['hashed_ip']}|{familia_navegador(c['header'].get('user-agent'))}".encode()).hexdigest()[:12]
        inicio = c["conversation"][1]["timestamp"]       # 1ª resposta do assistente: as falas do usuário não têm horário
        conversa_id = sha256(f"{c['hashed_ip']}|{c['conversation_hash']}|{inicio}".encode()).hexdigest()   # o hash sozinho NÃO é chave única
        db.execute("""
            INSERT INTO analytics.conversas (conversa_id, usuario_id, inicio, fim, modelo, turnos, pais)
            VALUES (%(conversa_id)s, %(usuario_id)s, %(inicio)s, %(fim)s, %(modelo)s, %(turnos)s, %(pais)s)
            ON CONFLICT (conversa_id) DO UPDATE SET fim = EXCLUDED.fim, turnos = EXCLUDED.turnos
              WHERE EXCLUDED.fim > analytics.conversas.fim      -- conversa que continua: guarda o fim mais recente
        """, {"conversa_id": conversa_id, "usuario_id": usuario_id, "inicio": inicio, "fim": c["timestamp"],
              "modelo": c["model"], "turnos": c["turn"], "pais": c["country"]})
```
**Causa (endpoint):** `min(ultimo_turno)`, `date_trunc('week', ...)` em UTC e `> primeira_vez + interval '1 hour'`. A correção mais segura é **tirar a regra do endpoint**: a sessão, o
retorno e a elegibilidade são calculados na carga (uma vez, testados) e o endpoint só lê.
```sql
-- na carga, por usuário (sessão nova quando passam mais de 30 min do fim da conversa anterior)
WITH o AS (
  SELECT usuario_id, inicio, fim,
         CASE WHEN lag(fim) OVER w IS NULL OR inicio - lag(fim) OVER w > interval '30 minutes' THEN 1 ELSE 0 END AS nova
  FROM analytics.conversas WHERE pais = $1
  WINDOW w AS (PARTITION BY usuario_id ORDER BY inicio, fim)),
s AS (SELECT *, sum(nova) OVER (PARTITION BY usuario_id ORDER BY inicio, fim) AS sessao,
             min(inicio) OVER (PARTITION BY usuario_id) AS primeira FROM o)
SELECT usuario_id, min(primeira) AS primeira_vez,
       bool_or(sessao > 1 AND inicio <= primeira + interval '7 days') AS voltou_7d      -- a própria sessão da 1ª experiência não conta
FROM s GROUP BY usuario_id;
-- semana no fuso do país: date_trunc('week', primeira_vez AT TIME ZONE 'America/Sao_Paulo')
-- elegível: só entra no retorno quem tem a janela de 7 dias fechada antes do fim dos dados
```
```ts
// app/api/retencao/coortes/route.ts: o endpoint só lê o que foi calculado e testado na carga
const { rows } = await db.query(
  `SELECT semana, novos, elegiveis, voltaram_7d, taxa, ic_lo, ic_hi
     FROM gold.agg_retorno_semana
    WHERE pais = $3 AND semana >= $1 AND semana < $2
    ORDER BY semana`,
  [inicio, fim, pais],
);
```
Esta correção **já está implementada e testada** neste projeto: `etl/camadas/silver/ (construir.py e sql.py)` (identidade, sessão, retorno, elegibilidade) e `etl/tests/test_incidente.py`
(o teste dourado: atualizar o navegador não cria outro usuário e a "primeira vez" é o início da conversa, em fuso do país).

## 4. O que mais fazer além de corrigir, e como evitar a recorrência
**Depois da correção:**
1. **Reprocessar todo o histórico** a partir da bruta: mudar a identidade muda **todos** os números passados, não só a semana de 20/11. Comparar antes e depois e publicar a nota de correção.
2. **Varrer o que usa a mesma identidade:** "usuários novos", retorno por tema e por modelo, comparações entre países e qualquer decisão já tomada com esses números.
3. **Confirmar o gatilho** (consultas do item 2) e registrá-lo no pós-incidente; se for tráfego automatizado, filtrá-lo à parte.
4. **Pós-incidente sem culpados** (linha do tempo, causa, o que detectou, o que atrasou).

**Para não voltar a acontecer** (as quatro camadas do item 4.1):
- **Teste que reproduz o incidente** (já escrito, `etl/tests/test_incidente.py`) e testes de contrato dos parâmetros da definição (gap 30 min, janela 7 dias, lavagem 30 dias). 189 testes em `docs/TESTES.md`.
- **Reconciliação automática:** toda semana, calcular o retorno também por uma definição simples e estável (IP, como o relatório do time) direto da bruta e comparar com o dashboard.
  Alerta se a diferença passar de ~5 pontos ou se `novos` variar mais de 30% de uma semana para outra.
  **Implementado como alerta semanal** (`etl/comum/anomalia_semanal.py`, em toda carga): cada semana é comparada com as 6 anteriores (novos, taxa e a proporção de "novos" cujo endereço já tinha aparecido com outra pessoa) e o diagnóstico aponta a camada. Os limites foram **calibrados nos dados reais** (30% de variação gerava 406 alertas em 202 países, que era ruído; o alerta de hoje exige 50% de alta e desvio robusto ≥ 5). O erro do incidente é reproduzido pelo cenário `incidente_navegador` (e a correção, por `incidente_navegador_corrigido`) em `docs/PREVENCAO_DE_DIVERGENCIAS.md`.
- **Indicadores de saúde da identidade** no monitoramento: razão `usuario_id distintos ÷ hashed_ip distintos` por dia (na nossa base é 1,06 com a definição adotada e sobe para 1,21 se o user-agent bruto entrar na identidade; alerta acima de ~1,3) e a lista de user-agents novos. **Implementado por carga** como o sinal "pessoas por endereço" (sobe 10% ou mais em relação à carga anterior: alerta), em `etl/comum/anomalia.py`.
- **Coorte com janela aberta aparece marcada** ("em andamento") e nunca entra na taxa.
- **A resposta do endpoint traz a versão da definição** (`definicao: "retorno_7d@v1"`) e o `request_id`, para ligar um número da tela à carga que o gerou.
- **Mudança de definição passa por revisão:** a definição vive num arquivo único, com testes; o portão do ETL compara os números novos com os validados antes de publicar.

## 5. O que eu diria à gerente de produto
**Durante (hoje, em poucas linhas, sem jargão):**
> "O gráfico mostra uma queda para 18%, mas **estamos investigando uma falha de medição**, não uma queda real. O relatório do time de dados, que usa outra forma de contar, mostra o
> retorno estável em ~30%. Pelo que já vimos, o gráfico contou como 'novas' cerca de 860 pessoas que já usavam o produto. **Peço que não tome decisão de produto com esse número por enquanto.**
> Volto com a causa confirmada e o número corrigido até [horário combinado]."

**Depois (quando a causa estiver confirmada e corrigida):**
> "**O que aconteceu:** o painel identificava uma pessoa pelo endereço e pelo navegador; quando muita gente atualizou/mudou o navegador na semana de 20/11, o painel as contou como novas e o retorno
> parecia cair. **O que mudou para você:** o retorno real da semana é ~30%; o histórico foi recalculado (nota de correção anexa, com os números antes e depois); nenhuma decisão baseada no 18% deve ser mantida.
> **O que mudamos:** a forma de identificar pessoas não depende mais da versão do navegador, há testes que reproduzem este caso e uma conferência automática toda semana contra um segundo método,
> com alerta para o time antes de você ver. **Seus números anteriores:** [lista dos que foram afetados e o impacto de cada um]."
