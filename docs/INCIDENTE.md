# Incidente: "o retorno caiu de 31% para 18%" (PDF, seção 4.2)

**Resposta em uma frase:** a causa no código está na carga: o `usuario_id` usa o user-agent bruto (`hashed_ip|user-agent`), então a mesma pessoa vira "nova" quando o user-agent muda. O que os dados do enunciado não provam é o que mudou em 20/11.

## 1. Por onde começo
Pelo número, não pelo código. Retorno = `voltaram ÷ novos`; olho cada parte separada:

| Semana | Dashboard: novos | voltaram | **retorno** | Relatório: novos | voltaram | **retorno** | Novos a mais no dashboard |
|---|---:|---:|---:|---:|---:|---:|---:|
| 06/11 | 1.210 | 375 | **31,0%** | 1.150 | 345 | **30,0%** | 60 |
| 13/11 | 1.188 | 368 | **31,0%** | 1.131 | 351 | **31,0%** | 57 |
| 20/11 | **2.034** | 366 | **18,0%** | 1.172 | 352 | **30,0%** | **862** |

- Os **voltaram não mudam** (375, 368, 366). A queda vem do **denominador**: 862 "novos" a mais.
- O relatório conta por `hashed_ip` e fica em ~30%. São duas definições de "pessoa" que divergiram.
- Perguntas ao time: mesmo período, fuso e filtros nos dois? Houve deploy ou mudança de proxy em torno de 20/11? A semana de 27/11 voltou ao normal?

## 2. Em qual camada está a falha
**Na carga.** Evidências:
- Tela e API só repetem a base (a resposta `req_4c19a2` já traz 2.034).
- O relatório lê a base bruta e fica estável.
- No código da carga a chave inclui o user-agent com a versão do navegador. É o único ponto que faz o dashboard contar mais "novos" que o relatório na mesma base.

**Consulta de confirmação** (base bruta). Conta os "novos" por semana das duas formas; a diferença são os **fantasmas**: IPs que já existiam, contados de novo por terem outro user-agent.
```sql
WITH par AS (                      -- cada combinação IP + user-agent e quando apareceu
  SELECT hashed_ip, header->>'user-agent' AS ua, min(primeira_resposta_ts) AS primeira_par
  FROM bronze.wildchat WHERE hashed_ip IS NOT NULL AND primeira_resposta_ts IS NOT NULL
  GROUP BY 1, 2),
ip AS (SELECT hashed_ip, min(primeira_par) AS primeira_ip FROM par GROUP BY 1)
SELECT date_trunc('week', timezone('America/Sao_Paulo', p.primeira_par))::date AS semana,
       count(*)                                                AS novos_ip_e_ua,   -- como o dashboard conta
       count(*) FILTER (WHERE p.primeira_par = i.primeira_ip)  AS novos_ip,        -- como o relatório conta
       count(*) FILTER (WHERE p.primeira_par > i.primeira_ip)  AS fantasmas        -- = novos_ip_e_ua - novos_ip
FROM par p JOIN ip i USING (hashed_ip)
GROUP BY 1 ORDER BY 1;
```
Resultado na nossa base (WildChat inteiro; a última linha soma todas as semanas):

| Semana | IP + user-agent (dashboard) | IP (relatório) | Fantasmas | % dos novos |
|---|---:|---:|---:|---:|
| 06/11 | 5.881 | 4.204 | 1.677 | 29% |
| 13/11 | 5.972 | 4.435 | 1.537 | 26% |
| **20/11** | **6.822** | **5.370** | **1.452** | **21%** |
| 27/11 | 8.001 | 6.440 | 1.561 | 20% |
| **Total** | **229.017** | **178.725** | **50.292** | **22%** |

- As duas definições contam diferente: o dashboard dá 28% mais "pessoas" que o relatório.
- **Parte disso é erro comprovado:** em 53% dos fantasmas (26.628) o navegador e o sistema são os mesmos e só a **versão** mudou, ou seja, a mesma pessoa contada duas vezes. Nos outros 47% pode ser outro aparelho ou outra pessoa no mesmo IP; sem ID de usuário, não dá para provar qual definição está certa.
```sql
-- fantasmas em que só a versão mudou (números do user-agent trocados por N)
WITH par AS (
  SELECT hashed_ip, min(primeira_resposta_ts) AS primeira_par,
         regexp_replace(coalesce(header->>'user-agent', ''), '[0-9]+(\.[0-9]+)*', 'N', 'g') AS modelo
  FROM bronze.wildchat WHERE hashed_ip IS NOT NULL AND primeira_resposta_ts IS NOT NULL
  GROUP BY hashed_ip, header->>'user-agent'),
r AS (SELECT *, min(primeira_par) OVER (PARTITION BY hashed_ip) AS primeira_ip,
                min(primeira_par) OVER (PARTITION BY hashed_ip, modelo) AS primeira_modelo FROM par)
SELECT count(*) FILTER (WHERE primeira_par > primeira_ip) AS fantasmas,
       count(*) FILTER (WHERE primeira_par > primeira_ip AND primeira_par > primeira_modelo) AS so_versao
FROM r;
```
- **Não há pico em 20/11:** 1.452 fantasmas, entre 1.537 e 1.561 nas semanas vizinhas. O salto do enunciado só se verifica na base da empresa.

**Ponto fraco da hipótese.** No enunciado os "voltaram" não sobem (366) mesmo com 862 "novos" a mais. Se fossem as mesmas pessoas com a versão nova, parte delas voltaria. Isso sugere ids de uso único (robô ou proxy que troca o user-agent) ou um filtro diferente entre dashboard e relatório. Para achar o gatilho, olho os user-agents dos fantasmas daquela semana:
```sql
-- (usa as CTEs par e ip da primeira consulta)
SELECT p.ua, count(*) AS fantasmas
FROM par p JOIN ip i USING (hashed_ip)
WHERE p.primeira_par > i.primeira_ip
  AND date_trunc('week', timezone('America/Sao_Paulo', p.primeira_par)) = timestamp '2023-11-20'
GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
```
Poucos valores novos concentrando quase tudo = atualização de versão ou proxy; muitos valores diferentes, cada um com poucos casos = robô. Na nossa base os maiores são a versão vigente de cada navegador (Chrome 119 no Windows: 359 de 1.452), toda semana, sem degrau em 20/11. Também o relatório por IP é imperfeito: quem divide um IP é contado como uma só pessoa.

## 3. Código que causa o problema e a correção
**Causa:** `chave = f"{c['hashed_ip']}|{c['header']['user-agent']}"`. **Correção:** a identidade usa a família do navegador e o sistema, sem versão:
```python
def familia_navegador(ua: str | None) -> str:
    """'Chrome/Windows': família + sistema, SEM número de versão (BDR-001)."""
    ua = ua or ""
    nav = ("Edge" if "Edg/" in ua else "Opera" if "OPR/" in ua else "Firefox" if "Firefox" in ua
           else "Chrome" if "Chrome" in ua else "Safari" if "Safari" in ua else "Outro")
    so = ("Android" if "Android" in ua else "iOS" if re.search("iPhone|iPad", ua) else "Windows" if "Windows" in ua
          else "Mac" if "Mac OS" in ua else "Linux" if "Linux" in ua else "Outro")
    return f"{nav}/{so}"

usuario_id = sha256(f"{c['hashed_ip']}|{familia_navegador(c['header'].get('user-agent'))}".encode()).hexdigest()[:12]
```
Já está implementado em `etl/camadas/silver/`, com o teste `etl/tests/test_incidente.py` (atualizar o navegador não cria outro usuário). A regra de retorno e semana também sai do endpoint e vai para a carga; o endpoint só lê `gold.agg_retorno_semana`.

## 4. Além de corrigir, e como evitar que volte
- **Reprocessar todo o histórico** (mudar a identidade muda os números passados), avisar quem usou esses números e registrar a causa no pós-incidente, sem culpados.
- **Teste que reproduz o incidente** (`etl/tests/test_incidente.py`).
- **Alerta semanal** (`etl/comum/anomalia_semanal.py`): compara cada semana com as 6 anteriores; semana com pico **retém a carga** e o cliente continua vendo os números anteriores. O cenário `incidente_navegador` reproduz o erro (README, seção 8).
- **Rastreio:** toda resposta da API traz `X-Versao-Definicao`, `X-Carga-Id` e `X-Request-Id`, para ligar um número da tela à carga que o gerou.
