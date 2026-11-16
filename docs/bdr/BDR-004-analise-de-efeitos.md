# BDR-004: análise dos efeitos no retorno em 7 dias (causa x seleção)

Status: resultados estáveis (reprodutíveis entre cargas); validação independente pendente (o efeito bruto se confere em SQL: `docs/CONFERIR_NUMEROS.md`, seção 3).
Código: `etl/camadas/gold/efeitos.py` (grava `gold.efeito_fator`) e `analise/04_sensibilidade.py`.

> **Correção de uma versão anterior deste documento.** A primeira versão trazia números que mudavam a cada carga
> (recusa -10,4; -10,8; -9,6): a validação cruzada dependia da ordem em que o banco devolvia as linhas. Agora as linhas
> são ordenadas por `usuario_id` e duas cargas seguidas dão exatamente o mesmo número. Com isso, duas conclusões
> mudaram: recusa e tamanho do pedido NÃO são frágeis ao recorte (eram ruído), mas recusa e saudação NÃO sobrevivem
> à correção para múltiplos testes. O ruído da divisão em dobras é de cerca de ±1 pp (ver sensibilidade).

## Pergunta e estimando
O que muda a chance de uma pessoa (usuário, BDR-001) voltar em até 7 dias? Para cada fator comparamos dois grupos de
usuários elegíveis do Brasil (n = 2.234) e reportamos a **diferença de retorno em pontos percentuais (pp)** com IC de 95%.

## Método
- **Efeito bruto:** diferença simples entre grupos (o que um olhar descritivo concluiria; IC de Wald).
- **Efeito ajustado (principal):** estimador **AIPW** (duplamente robusto): combina um modelo de propensão (quem recebe o
  fator) e um modelo de resultado (quem volta); consistente se um dos dois estiver certo. Regressão logística L2,
  validação cruzada em 5 dobras (semente fixa, linhas em ordem fixa), corte do escore em [0,025; 0,975], erro padrão pela
  função de influência.
- **Sobreposição:** % de usuários com probabilidade de tratamento entre 5% e 95% (se baixa, o contraste extrapola).
- **E-value:** força mínima (razão de risco) que um confundidor NÃO medido precisaria ter, com o tratamento e com o
  retorno, para anular o efeito (limite do IC). 1,0 = o IC já inclui zero.
- **Classificação:** *alavanca* (o produto controla: modelo, recusa, tamanho da resposta) x *perfil* (descreve quem chega:
  tema, turnos, tamanho do pedido, horário, dia, idioma). Só alavancas sustentam "se mudarmos X, o retorno muda".
- **Covariáveis (anteriores ao fator):** mês de chegada, período do dia, fim de semana, sistema, navegador, estado (top 5);
  conforme o fator, também modelo, tema, tamanho do pedido e idioma. Cada linha de `efeito_fator` guarda a lista usada.

## Resultados (Brasil, pp de retorno; ordenado pelo tamanho do efeito ajustado, como pede o enunciado)
| Fator (contraste) | Tipo | Bruto | Ajustado [IC 95%] | E-value (IC) |
|---|---|---|---|---|
| Recusa na 1ª resposta (com x sem) | alavanca | -8,9 | **-9,6 [-17,3; -1,9]** | 1,38 |
| Tema Saudação x Conhecimento/pergunta | perfil | -10,9 | **-8,1 [-14,3; -1,8]** | 1,37 |
| Turnos na 1ª conversa (2+ x 1) | perfil | +6,5 | **+8,7 [+3,3; +14,1]** | 1,62 |
| Tamanho do 1º pedido (longo x curto) | perfil | +7,4 | **+6,3 [+2,2; +10,5]** | 1,45 |
| Demais temas (Vazio, Tarefa escolar, Persona, Ficção, Escrita, Tecnologia, Outro) x Conhecimento | perfil | -- | IC inclui zero, muito largos (até ±15 pp) | 1,0 |
| Horário (noite), Dia (fim de semana), Idioma (inglês) | perfil | -- | IC inclui zero (±4 a 5 pp) | 1,0 |
| **Modelo (GPT-4 x GPT-3.5)** | alavanca | +0,8 | **-0,6 [-5,0; +3,9]** | 1,0 |
| **Tamanho da 1ª resposta (longa x curta)** | alavanca | +4,1 | **+0,1 [-5,3; +5,5]** | 1,0 |

Leituras: (1) o ganho bruto de resposta longa (+4,1) **some** depois de ajustar (+0,1): era tema, pedido e modelo, não a
resposta; (2) GPT-4 não mostra efeito detectável (o bruto já era ~0; o ajuste de calendário importa porque as versões do
modelo mudam no tempo); (3) com 2.234 usuários os intervalos são de ±5 pp: "sem efeito detectável" NÃO é "efeito zero";
(4) os temas raros têm intervalos tão largos que não permitem concluir nada.

## Sensibilidade (analise/04_sensibilidade.py)
Mudar semente e número de dobras move o ponto em até ~±1 pp, sempre dentro do IC (recusa -9,1 a -11,4; turnos +7,1 a +8,7;
pedido longo +6,3 a +7,3; saudação -7,7 a -9,3). Excluir usuários com mais de 20 conversas e restringir a quem teve só 1
conversa na 1ª sessão **mantêm sinal e IC sem zero nos quatro efeitos** (recusa -9,4 [-17,0; -1,8]; saudação -7,1
[-14,0; -0,2]; turnos +9,6 [+3,2; +15,9]; pedido longo +4,9 [+0,5; +9,3]). Modelo e resposta longa seguem em torno de zero em todas
as variantes. Ressalva: o limite superior da saudação (-0,2) e o inferior do pedido longo (+0,5) ficam quase em zero.

## Multiplicidade
16 contrastes testados. Com Bonferroni (p < 0,003) e com Benjamini-Hochberg (5%), só **turnos** (p≈0,002) e **tamanho do
pedido** (p≈0,003) permanecem. **Saudação** (p≈0,011) e **recusa** (p≈0,015) valem como **indícios**: significativos
isoladamente, mas não depois de corrigir por testar 16 coisas.

## O que a análise prova e o que não prova
- Prova: a associação ajustada pelo que observamos (calendário, dispositivo, região, tema, pedido, idioma, modelo).
- **Não prova causa.** Fica confusão não medida: o engajamento prévio da pessoa. Turnos e tamanho do pedido são em boa parte
  *comportamento de quem já está engajado* (por isso são "perfil", não alavanca). O E-value (1,4 a 1,6) mostra que um
  confundidor moderado basta para anular os quatro efeitos.
- Só um experimento (teste A/B: mudar a resposta a saudações ou a política de recusa para metade dos usuários) separa causa.

## Limites
Amostra pequena (poder baixo); "usuário" = navegador em uma rede (BDR-001, viés em ambos os sentidos); tema e recusa são
heurísticas ainda não validadas à mão (BDR-003); sobreposição de 67% para o modelo (as versões do GPT mudam no tempo);
a recusa é medida só na abertura da 1ª resposta.

## Achados candidatos para o cliente (a validar com o autor antes de entrar no documento)
1. **Quem abre só com uma saudação volta ~8 pp menos** (17% dos novos usuários; indício robusto ao recorte). Decisão:
   responder a "oi" com exemplos do que o assistente faz (onboarding na própria conversa) e testar por A/B.
2. **Recusas na primeira resposta custam ~10 pp de retorno** (indício; alavanca). Decisão: auditar recusas e desculpas
   em primeiras respostas, reduzir falsas recusas e testar respostas alternativas.
3. **Trocar para um modelo maior ou respostas mais longas não mostra ganho de retorno** (-0,6 e +0,1 pp, IC ±5). Decisão:
   não justificar o custo de GPT-4 por retenção; usar turnos e pedido longo (únicos efeitos que resistem à correção para
   múltiplos testes) como **sinal precoce** de engajamento, não como alavanca.

## Atualização da exploração (12/11/2026, `docs/EDA.md`)
Comparações simples **dentro de cada família de modelo** (sem ajuste, intervalos isolados) refinam os achados 1 e 2:
- **Saudação** pesa nos dois modelos: GPT-3.5 −10,1 pp [−15,4; −4,8] (n=237) e GPT-4 −11,9 pp [−18,3; −5,6] (n=149). Fica **mais firme**.
- **Recusa** depende do modelo: GPT-4 −14,1 pp [−21,3; −6,9] (n=88); GPT-3.5 −4,7 pp [−12,5; +3,0] (n=110, inclui zero); na versão 3.5-0301, −0,2 pp [−12,2; +11,7] (59 recusas). O −9,6 médio mistura os dois: é um **indício concentrado no GPT-4**.
- A versão do modelo (não só a família) muda a taxa de recusa de 2,5% a 13,1%; o ajuste do AIPW usa a família e o mês de chegada, então a confusão com a versão **não está totalmente tratada**.
