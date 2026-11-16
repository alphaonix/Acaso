# BDR-003: classificação do tema da primeira conversa

Status: aceita como premissa de trabalho; pendente de validação manual (amostras em `exports/amostra_validacao_*.csv`; ver README, seção 13).

## Contexto
O PDF pede o tema como variável da primeira experiência e que, se usarmos IA para classificar, expliquemos como
conferimos o resultado. A base não traz tema. Os primeiros pedidos reais do Brasil mostram: 784 de 11.621 com até 12
caracteres (saudações como "oi" e "hello"), 141 vazios, prompts de persona/jailbreak repetidos, geradores de prompt
para imagem, ficção (inclusive adulta), dúvidas técnicas, tarefas escolares e perguntas de conhecimento.

## Opções consideradas
1. **Regras de palavras-chave em ordem de prioridade (SQL).** Grátis, reproduzível, auditável, roda na carga. Erra em
   pedidos ambíguos e em vocabulário fora das listas.
2. **LLM na AWS (Bedrock) por pedido.** Mais preciso e entende contexto; custo e latência por conversa, exige
   credenciais AWS e não roda no `docker compose` de quem avalia sem chave. O PDF exige que o LLM do dashboard fique na AWS.
3. **Embeddings + agrupamento.** Descobre temas sem taxonomia, mas os grupos precisam de nome e são difíceis de explicar a
   quem não é técnico.

## Decisão
Opção 1 para a entrega (reproduzível localmente, custo zero, regras visíveis no SQL), com **validação manual por
amostra estratificada** (até 8 por tema, `exports/amostra_validacao_tema.csv`) e taxa de acerto registrada.
Opção 2 descrita como evolução na AWS (Bedrock com modelo pequeno, classificação em lote na carga, resultado gravado
na base analítica e não calculado por consulta), a decidir com o cliente pelo custo.

## Taxonomia (11 classes, primeira regra que casa vence)
01 Vazio · 02 Saudação · 03 Prompt de imagem · 04 Persona/roleplay · 05 Adulto/sensível · 06 Tecnologia/código ·
07 Tarefa escolar/acadêmica · 08 Escrita/edição/tradução · 09 Ficção/criação · 10 Conhecimento/pergunta · 11 Outro.
A ordem importa (ex.: um pedido de ficção adulta cai em "Adulto/sensível", não em "Ficção").

## Resultado da 1ª versão (usuários, 1ª conversa)
Outro = 20,2% (a primeira versão, com 10 classes e regras mais estreitas, deixava 35,5% em Outro; o ajuste veio de
olhar 60 casos de "Outro"). Saudação 17,0%, Conhecimento/pergunta 24,0%, Escrita/edição/tradução 10,5%,
Tecnologia/código 10,1%. Os retornos brutos por tema (14,8% em Saudação a 38,1% em Adulto/sensível) são só
descritivos: não controlam confusão e não têm intervalo de confiança.

## Riscos e limites
- É heurística: palavras amplas ("texto", "programa", "aula") geram falsos positivos; o idioma é majoritariamente PT/EN.
- Temas pequenos (Prompt de imagem 16 usuários, Adulto 21) terão intervalos largos; o dashboard mostra o aviso.
- Classificar só a primeira conversa ignora o que a pessoa fez depois (decisão coerente com "primeira experiência").
- Se a taxa de acerto na validação for baixa, subir para a opção 2 em amostra para medir o erro da heurística.
