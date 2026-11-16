# BDR-004: efeito de cada fator no retorno em 7 dias

Status: aceita; resultados reproduzíveis (duas cargas dão o mesmo número). O efeito bruto se confere em SQL (`docs/CONFERIR_NUMEROS.md`, seção 3). Código: `etl/camadas/gold/efeitos.py` (grava `gold.efeito_fator`) e `analise/04_sensibilidade.py`.

## Contexto
Comparar grupos (por exemplo, resposta longa x curta) mistura efeito com seleção: quem escreve pedidos longos já é outro tipo de pessoa. O cliente quer saber o que o produto pode mudar, então é preciso separar **alavanca** de **perfil** e dizer o quanto confiar em cada número. Pergunta: o que muda a chance de uma pessoa voltar em até 7 dias? Para cada fator comparamos dois grupos das 2.234 pessoas elegíveis do Brasil e reportamos a diferença em pontos percentuais (pp), com intervalo de 95%.

## Opções
1. **Diferença bruta com intervalo.** Fácil de conferir em SQL, mas não ajusta nada (mantida como comparação).
2. **Regressão logística única.** Fácil de explicar, mas depende de um só modelo estar certo.
3. **AIPW com validação cruzada.** Combina dois modelos e basta um estar certo; custa mais explicar.
4. **Pareamento por escore de propensão.** Descarta dados e é instável com 2.234 pessoas.

## Decisão
Opção 3 como estimativa principal, com o bruto ao lado.
- **AIPW:** modelo de propensão (quem recebe o fator) e modelo de resultado (quem volta), regressão logística L2, 5 dobras com semente fixa e linhas ordenadas, escore cortado em [0,025; 0,975], erro padrão pela função de influência.
- **Covariáveis (anteriores ao fator):** mês de chegada, período do dia, fim de semana, sistema, navegador e estado; conforme o fator, também modelo, tema, tamanho do pedido e idioma.
- **Multiplicidade:** 16 contrastes, com Bonferroni (p < 0,003) e Benjamini-Hochberg (5%). Só passa quem "resiste à correção"; os demais são "indício".
- **E-value:** força mínima que um fator não medido teria de ter para anular o efeito.
- **Classificação:** *alavanca* (o produto controla: modelo, recusa, tamanho da resposta) x *perfil* (descreve quem chega: tema, turnos, tamanho do pedido, horário, dia, idioma). Só alavancas sustentam "se mudarmos X, o retorno muda".

## Resultados (Brasil, em pp de retorno, ordenados pelo tamanho do efeito)
| Fator (contraste) | Tipo | Bruto | Ajustado [IC 95%] | Leitura |
|---|---|---|---|---|
| Recusa na 1ª resposta (com x sem) | alavanca | −8,9 | **−9,6 [−17,3; −1,9]** | indício |
| Turnos na 1ª conversa (2 ou mais x 1) | perfil | +6,5 | **+8,7 [+3,3; +14,1]** | resiste à correção |
| Tema Saudação x Conhecimento/pergunta | perfil | −10,9 | **−8,1 [−14,3; −1,8]** | indício |
| Tamanho do 1º pedido (longo x curto) | perfil | +7,4 | **+6,3 [+2,2; +10,5]** | resiste à correção |
| Modelo (GPT-4 x GPT-3.5) | alavanca | +0,8 | −0,6 [−5,0; +3,9] | sem efeito detectável |
| Tamanho da 1ª resposta (longa x curta) | alavanca | +4,1 | +0,1 [−5,3; +5,5] | sem efeito detectável |
| Demais temas, horário, dia, idioma | perfil | – | intervalos incluem zero (±4 a ±15 pp) | sem efeito detectável |

- O ganho bruto da resposta longa (+4,1) **some** depois de ajustar (+0,1): era tema, pedido e modelo.
- "Sem efeito detectável" não é "efeito zero": com 2.234 pessoas os intervalos são de cerca de ±5 pp.
- **Por modelo (sem ajuste):** a saudação pesa nos dois (GPT-3.5 −10,1 pp, GPT-4 −11,9 pp). A recusa pesa mais no GPT-4 (−14,1 pp, contra −4,7 no GPT-3.5, que inclui zero), mas a diferença entre os dois (−9,4 pp) não se distingue de acaso (p ≈ 0,08). A versão do modelo muda a taxa de recusa de 2,5% a 13,1%, e o ajuste usa a família e o mês, então essa confusão não está totalmente tratada.

## Sensibilidade
Mudar a semente e o número de dobras move o ponto em até ±1 pp, sempre dentro do intervalo. Excluir quem tem mais de 20 conversas, ou restringir a quem teve só 1 conversa na primeira sessão, mantém o sinal e o intervalo sem zero nos quatro efeitos (os limites mais próximos de zero são −0,2 na saudação e +0,5 no pedido longo). Modelo e resposta longa ficam perto de zero em todas as variantes.

## O que prova e o que não prova
- **Prova:** a associação ajustada pelo que observamos (calendário, aparelho, região, tema, pedido, idioma e modelo).
- **Não prova causa.** Falta o engajamento prévio da pessoa: turnos e tamanho do pedido são em boa parte comportamento de quem já está engajado (por isso são "perfil"). O E-value do limite do intervalo (1,4 a 1,6) mostra que um fator não medido moderado basta para anular os quatro efeitos.
- Só um teste A/B (por exemplo, mudar a resposta a saudações ou a política de recusa para metade das pessoas) separa causa.

## Limites
Poucas pessoas (poder baixo); "pessoa" é um navegador numa rede (BDR-001); tema e recusa são regras de palavras (BDR-003); a sobreposição é de 67% para o modelo (as versões do GPT mudam no tempo); a recusa é medida só no início da 1ª resposta.

## Achados para o cliente
1. **Quem abre só com uma saudação volta cerca de 8 pp menos** (17% das pessoas novas). Decisão: responder ao "oi" com exemplos do que o assistente faz e testar por A/B.
2. **Recusa ou ressalva na 1ª resposta custa cerca de 10 pp** (indício, alavanca). Decisão: revisar recusas desnecessárias e testar respostas alternativas.
3. **Modelo maior ou resposta mais longa não mostram ganho de retorno.** Decisão: não justificar o custo do GPT-4 por retenção; usar turnos e pedido longo como sinal precoce de engajamento, não como alavanca.
