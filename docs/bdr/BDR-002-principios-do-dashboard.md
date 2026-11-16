# BDR-002: princípios do dashboard

Status: aceita. Critério do PDF: cada tela se explica sozinha, cada número tem definição e fonte, cada efeito tem sua incerteza.

## Contexto
O público é de negócio, não técnico. Cartões com unidade ou denominador diferentes pareceram divergir na conferência, e uma taxa sem intervalo leva a decidir sobre ruído.

## Opções
1. **Painel enxuto, sem texto de apoio.** Menos trabalho, mas cada pessoa interpreta do seu jeito.
2. **Documentação à parte.** Explica, mas desatualiza e ninguém lê antes de olhar o gráfico.
3. **Definição junto do número, vinda de um catálogo único.** Mais metadados, uma fonte só.

## Decisão
Opção 3.
1. **Todo indicador tem definição.** O botão "i" mostra a pergunta, a fórmula, a unidade, o denominador, o período, a fonte e a amostra mínima. Taxas e efeitos trazem o intervalo de 95%.
2. **Amostra pequena:** com menos de 30 pessoas a tela mostra "amostra pequena demais", não o número.
3. **Explicação na própria tela:** a Visão geral abre com "De onde vêm estes dados". A aba **Ajuda** traz as palavras e regras, o que o painel mostra e nunca mostra, os problemas de qualidade e como classificamos recusa, tema e idioma.
4. **Associação não é causa:** todo efeito diz isso, e só um teste A/B confirma.
5. **Filtro de país** no cabeçalho, em todas as telas e endpoints (`?pais=`); padrão Brasil. Países com poucas pessoas mostram o aviso de amostra pequena. Tema e recusa só existem para o Brasil (único país com texto, ADR-002) e a tela mostra "indisponível" nos demais.

## Consequências
- Um catálogo (`etl/comum/definicoes.py`) alimenta o botão "i", o `docs/INDICADORES.md` e os testes. Uma definição muda num lugar só.
- Um teste compara o SQL de referência de cada indicador com o número da gold.
