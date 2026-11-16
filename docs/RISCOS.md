# Riscos e decisões em aberto (PDF, seção 4.3)

O que pode dar errado e o que eu levaria ao time ou ao cliente **antes** de implementar em produção, por estar fora do meu escopo.

## Principais riscos
| # | Risco | Por que importa | O que eu fiz / faria |
|---|---|---|---|
| 1 | **Não existe ID de usuário.** "Pessoa" = IP + família do navegador/sistema. | Todo indicador de retorno depende disso. O gap da sessão sozinho move o retorno de 19,6% a 26,3% (`docs/SENSIBILIDADE.md`). | Premissa registrada (BDR-001) e sensibilidade medida; teste que reproduz o incidente. Pedir ao cliente um identificador estável (login ou ID anônimo persistente). |
| 2 | **Privacidade e licença.** As conversas podem ter dado pessoal; a semente do Brasil leva o texto. | LGPD, reputação e uso indevido do dataset. | Repositório **privado**; a base analítica não guarda texto; o painel nunca mostra texto, IP nem usuário. Conferir a licença do WildChat antes de redistribuir. |
| 3 | **Associação não é causa.** Confusão não medida (engajamento prévio). | O cliente pode investir em algo que não funciona. | Efeitos ajustados com intervalo e E-value; só 2 de 16 efeitos resistem à correção para múltiplos testes. Propor teste A/B antes de qualquer investimento. |
| 4 | **Amostra pequena** (2.234 usuários elegíveis). | Intervalos de ±5 pp: "sem efeito detectável" não é "efeito zero". | A tela mostra o intervalo e esconde taxas com menos de 30 elegíveis. Mais dados, ou um experimento com poder calculado. |
| 5 | **Tema e recusa vêm de regras de palavras.** Conferência manual da recusa: 8 de 30 (27%) são recusa no sentido estrito; a do tema não foi medida. | Dois dos três achados dependem deles. | Ler a recusa como "recusa ou ressalva de IA" e tratar o achado 2 como indício; medir a precisão do tema e apertar a regra da recusa antes de apresentar como fato. Decidir se vale um LLM (Bedrock) e quanto custa. |
| 6 | **Só o Brasil tem texto**; outros países sem tema nem recusa; idiomas além de PT/EN sem regra. | O pedido de "outros países" cobre só parte do painel. | A tela diz "indisponível". Para estender: levar o texto, acrescentar idiomas e validar por idioma. |
| 7 | **Falta de dados** para responder melhor: avaliação do usuário (curtir/não curtir), custo e latência da resposta, tipo de conta. | O "porquê" fica sem sinal direto de qualidade. | Propor a instrumentação ao time do assistente (ver "Decisões"). |
| 8 | **Mudança de formato ou de definição.** A carga depende do formato do dado e das regras. | Um campo novo ou uma mudança silenciosa quebra o número (foi o caso do incidente). | Testes de contrato da definição, portão de qualidade no ETL e reconciliação semanal; definição versionada. |
| 9 | **Operação e custo na AWS** (quem opera, SLA, orçamento, retenção de logs). | O dashboard precisa de dono depois da entrega. | Custo estimado em `infra/README.md`: **≈ US$ 136 por mês em São Paulo** (≈ US$ 77 na Virgínia, que tira o dado do Brasil; ≈ US$ 190 com alta disponibilidade). Falta o cliente decidir região, SLA e o dono da operação. |
| 10 | **Leitura errada pelo negócio** (número sem incerteza vira certeza). | Decisões em cima de ruído. | Cada número com definição, intervalo e aviso de amostra pequena; tela "Ajuda". |

## Decisões que eu levaria antes de começar
| Decisão | Quem decide | Por que antes |
|---|---|---|
| Existirá um ID de usuário estável? Qual (login, cookie, dispositivo)? | Produto e Engenharia do cliente | Muda a definição de "pessoa" e todos os números. |
| O texto das conversas pode ser usado (e por quanto tempo)? Qual a base legal (LGPD)? | Jurídico e DPO do cliente | Define se tema, recusa e classificação por LLM podem existir. |
| Aceitam um **teste A/B** (saudação e política de recusa)? | Produto | É a única forma de separar causa de seleção. |
| Qual meta de retorno e qual o horizonte (7 dias é o certo)? Gap da sessão de 30 min serve ao produto? | Produto e Negócio | O indicador precisa refletir uma decisão que o cliente toma. |
| Quais países e idiomas, e com qual prioridade? | Negócio | Define fuso, tradução, classificação por idioma e custo. |
| Orçamento e dono da operação na AWS; uso de LLM (Bedrock) ou só regras? | Engenharia e Financeiro | Custo recorrente e responsabilidade em produção. |
| Que dado adicional será coletado (avaliação da resposta, latência, plano)? | Produto e Dados | Sem ele, o "porquê" continua indireto. |
| Quem aprova uma mudança de definição de indicador e como o histórico é comunicado? | Dados e Negócio | Evita que um número mude sem ninguém notar. |