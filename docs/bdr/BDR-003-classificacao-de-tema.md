# BDR-003: tema do primeiro pedido e recusa

Status: aceita. As regras e exemplos estão em `docs/REGRAS_DE_TEXTO.md`. A precisão do tema não foi medida.

## Contexto
O PDF pede o tema como variável da primeira experiência e que, se usarmos IA para classificar, expliquemos como conferimos. A base não traz tema. Os primeiros pedidos do Brasil mostram saudações, pedidos vazios, persona e jailbreak, prompts de imagem, ficção, dúvidas técnicas, tarefa escolar e perguntas de conhecimento.

## Opções
1. **Regras de palavras em ordem de prioridade (SQL).** Grátis, repetível, auditável. Erra em pedidos ambíguos.
2. **LLM na AWS (Bedrock) por pedido.** Mais preciso; tem custo e latência, e exige credencial AWS que o avaliador não tem no `docker compose`.
3. **Embeddings e agrupamento.** Descobre temas sem lista, mas os grupos precisam de nome e são difíceis de explicar.

## Decisão
Opção 1, para tema e para recusa. Opção 2 fica como evolução (classificar em lote na carga e gravar o resultado).
- **Tema:** 11 classes testadas em ordem sobre os 600 primeiros caracteres do pedido; vale a primeira que bate (por isso ficção adulta vira "Adulto/sensível"). Só o Brasil.
- **Recusa:** o início (300 caracteres) da primeira resposta casa uma lista de expressões ("desculp", "não posso", "I'm sorry", "as an AI"…). Só o Brasil. Marca 8,9% das pessoas (198 de 2.234).

## Resultado (Brasil, pessoas elegíveis, retorno bruto e sem ajuste)
| Tema | Pessoas | Retorno |
|---|---:|---:|
| Conhecimento/pergunta | 531 | 25,6% |
| Outro | 438 | 23,3% |
| Saudação | 386 | 14,8% |
| Escrita/edição/tradução | 244 | 27,5% |
| Tecnologia/código | 218 | 24,3% |
| Ficção/criação | 123 | 37,4% |
| Tarefa escolar/acadêmica | 99 | 26,3% |
| Persona/roleplay | 90 | 23,3% |
| Vazio | 69 | 17,4% |
| Adulto/sensível | 21 | 38,1% |
| Prompt de imagem | 15 | 13,3% |

Os retornos por tema são descritivos: sem ajuste e, nos temas pequenos, com intervalos largos. O efeito ajustado está no BDR-004.

## Riscos e limites
- É heurística: palavras amplas ("texto", "programa", "aula") dão falso positivo, e a versão 1 deixava 35,5% em "Outro" até ajustarmos as regras olhando 60 casos.
- A regra de recusa também pega avisos como "como uma IA…": leia como **recusa ou ressalva de IA**. Em uma amostra de 30 marcadas, 8 eram recusa estrita. Não medimos o que a regra deixa passar.
- Só se classifica a primeira conversa, coerente com "primeira experiência".
- Os testes fixam o comportamento atual (regressão); não medem a precisão.
