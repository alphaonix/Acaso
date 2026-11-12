# Como o dado vira o número da tela (passo a passo, com conferência)

Leia na ordem. Cada etapa tem: **a regra em uma frase**, **uma consulta para você conferir no DBeaver** (`localhost:5433`, banco
`retencao`, usuário `etl`) e **o resultado esperado** (números do Brasil, salvo quando dito). Nada aqui pede confiança: tudo se confere.
As mesmas conferências rodam sozinhas a cada carga (36 verificações, registradas em `ops.qa_resultado`); se uma falhar, a carga não é publicada.

```
arquivos (semente)  →  BRONZE (cópia)  →  SILVER (limpa, 1 linha por conversa e por usuário)  →  GOLD (resumos)  →  tela
```

## 1. Bronze: o dado como veio
**Regra:** `bronze.wildchat` é uma cópia fiel dos arquivos, sem limpar nada. Todos os países, uma linha por conversa.
```sql
SELECT count(*) FROM bronze.wildchat;    -- 837.989 (Brasil: 11.621)
```

## 2. Início e fim de cada conversa
**Regra:** o **início** é o horário da 1ª resposta do assistente (`primeira_resposta_ts`); o **fim** é o horário da última resposta
(`timestamp`). As mensagens do usuário não têm horário no WildChat (nenhuma, em nenhum país), por isso o início é a 1ª resposta.
Isso adianta o início em alguns segundos, o que não afeta um retorno medido em dias. Detalhes e prova no BDR-001.
```sql
SELECT count(*) AS linhas, count(primeira_resposta_ts) AS com_inicio FROM bronze.wildchat;   -- 837.989 e 837.989
```

## 3. O que sai da bronze para a silver
**Regra:** sai a conversa que (a) não tem horário de início, (b) não tem IP, ou (c) é cópia exata de outra (mesmo hash, IP e início).
```sql
SELECT motivo, count(*) FROM auditoria.registro_excluido GROUP BY 1;     -- duplicata_exata: 17 (nenhuma do Brasil)
SELECT * FROM auditoria.camadas WHERE pais = '(todos)' ORDER BY ordem;   -- 837.989 → 837.972 → 837.972
```
Fica a lei de conservação: **bronze = silver + excluídas** (837.989 = 837.972 + 17).

## 4. Quem é o "usuário"
**Regra:** não há ID de usuário na base. Usuário = IP (já anonimizado) + navegador/sistema sem número de versão (`Chrome/Windows`).
`usuario_id` é o hash dessa combinação. É uma aproximação: quem muda de rede ou aparelho vira outra pessoa; quem divide IP se mistura.
```sql
SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil';     -- 2.530 usuários (de 11.621 conversas)
```

## 5. Sessão
**Regra:** as conversas de um usuário em ordem de início. Se uma conversa começa **mais de 30 minutos depois do fim da anterior**,
abre uma **nova sessão**; senão continua na mesma.

## 6. Primeira vez
**Regra:** o início da primeira conversa do usuário. Modelo, idioma, turnos, tema e recusa do usuário são os dessa conversa.

## 7. Voltou em 7 dias?
**Regra:** `voltou_7d` = existe uma **sessão posterior** (da 2ª em diante) que começa **até 7 dias depois da primeira vez**.

## 8. Elegível
**Regra:** só entra no cálculo do retorno quem tem a janela inteira: a primeira vez precisa ser **30 dias depois do início dos dados**
do país (para não chamar de "novo" quem já usava antes) e **7 dias antes do fim** dos dados (para os 7 dias terem acontecido).
```sql
SELECT min(inicio_utc), max(inicio_utc) FROM silver.fato_conversa WHERE pais = 'Brazil';   -- em UTC: 09/04/2023 a 29/04/2024 (no horário de São Paulo: 08/04/2023 a 29/04/2024)
SELECT count(*) FILTER (WHERE elegivel) AS elegiveis,
       count(*) FILTER (WHERE elegivel AND voltou_7d) AS voltaram,
       round(count(*) FILTER (WHERE elegivel AND voltou_7d)::numeric / count(*) FILTER (WHERE elegivel), 4) AS retorno
FROM silver.fato_usuario WHERE pais = 'Brazil';                                           -- 2.234 | 530 | 0,2372
```
Esse 23,72% é o número principal da tela (retenção em 7 dias).

## 9. Audite um usuário (os passos 5 a 8, na mão)
```sql
SELECT * FROM auditoria.audite_usuario('00a3cf656f92');
```
| n | início (local) | min desde o fim anterior | sessão | dias desde a 1ª | dentro dos 7 dias | voltou (silver) | elegível |
|---|---|---|---|---|---|---|---|
| 1 | 17/02/2024 09:15 | | 1 | 0,00 | não | sim | sim |
| 2 | 22/02/2024 19:22 | 7.796 | 2 | 5,42 | **sim** | sim | sim |
| 3 | 22/02/2024 20:22 | 59 | 3 | 5,46 | sim | sim | sim |
| 4 | 25/02/2024 18:11 | 4.187 | 4 | 8,37 | não | sim | sim |

Leitura: cada intervalo passa de 30 min, então cada conversa abre uma sessão. A conversa 2 ocorre 5,42 dias após a primeira, dentro
dos 7: **voltou**. A primeira vez (17/02/2024) está entre 08/05/2023 (início + 30 dias) e 22/04/2024 (fim − 7 dias): **elegível**.
Troque o `usuario_id` por qualquer outro para auditar outro usuário.

## 10. Recusa e tema (só Brasil, por desenho)
**Regra:** só a semente do Brasil traz o texto das conversas; os outros países vêm sem texto (o texto truncado deles pesaria cerca de
186 MB, acima do limite do repositório). Por isso:
- **Recusa na 1ª resposta:** os primeiros 300 caracteres da 1ª resposta casam com padrões de recusa ou desculpa (PT/EN). Brasil: 198 de
  2.234 elegíveis = **8,9%** (cartão da tela "Visão geral"). Em outros países a tela mostra "indisponível", não um zero.
- **Tema do pedido:** os primeiros 600 caracteres do 1º pedido, em 11 temas, e a primeira regra que casa vence.
- **As regras são em português e inglês.** Entre os outros países, 58% das conversas são em inglês, mas 14% em chinês, 10% em russo e o
  restante em outros idiomas, onde as regras classificariam quase tudo como "Outro". Para estender a outro país: levar o texto na
  semente (ou calcular tema e recusa ao gerá-la) e **acrescentar os padrões do idioma**. O resto do pipeline já funciona para todos.
- Validação por amostra manual das duas regras: `exports/amostra_validacao_*.csv` (pendente de conferência humana, ver `VALIDACAO.md`).

## 11. Gold: o que a tela lê
Resumos prontos por país, semana e fator (`gold.agg_retorno_semana`, `gold.agg_retorno_fator`) e os efeitos ajustados
(`gold.efeito_fator`). A gold tem as mesmas 837.972 conversas da silver, só agrupadas. Cada taxa vem com intervalo de confiança de
95% (Wilson) e é escondida quando a amostra é menor que 30.

## 12. As 36 conferências do portão (transição → o que protege)
| transição | n | exemplo |
|---|---|---|
| bronze_arquivos | 5 | linhas da bronze = linhas dos arquivos de origem |
| bronze_silver | 3 | bronze = silver + excluídas |
| silver_interna | 7 | soma das conversas por usuário = conversas; **retorno, elegibilidade e primeira vez recalculados a partir das conversas = os da silver** |
| silver_gold | 8 | a gold soma o que a silver tem |
| efeitos | 3 | intervalo contém a estimativa; nenhum grupo com menos de 30 |
| validados | 10 | números do Brasil conferidos à mão (Power BI e DBeaver) |

O recálculo da linha `silver_interna` parte só das conversas e refaz as sessões, então não repete a conta da silver. Hoje ele dá **0
divergências nos 197.319 usuários**. Ele confirma que a implementação segue a regra; se a regra em si está certa, o passo 9 deixa você
conferir à mão.

## 13. Limites a declarar
- Usuário = IP + navegador/sistema é uma aproximação (o BDR-001 mostra o impacto de cada alternativa).
- Fuso único por país: aproximado para países com mais de um fuso (a tela avisa).
- Tema e recusa são regras de palavras, não um modelo, e só existem onde há texto e regra para o idioma.
- Retenção observacional: a análise de efeitos separa o que é causa do que é seleção com ajuste e intervalo (BDR-004), mas não prova causa.
