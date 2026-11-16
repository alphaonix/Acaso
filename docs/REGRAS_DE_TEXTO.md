# Regras de texto: recusa, tema e idioma

Três variáveis vêm de **regras de palavras em SQL**, sem IA. As regras ficam em [`etl/comum/definicoes.py`](../etl/comum/definicoes.py) (recusa e tema) e [`etl/camadas/gold/sql.py`](../etl/camadas/gold/sql.py) (idioma x navegador). Mudar uma regra muda o número no painel, e a carga acusa a diferença nas conferências. A mesma explicação está na aba **Ajuda** do painel.

Tema e recusa só existem para o **Brasil**, o único país cuja semente traz o texto. Os números abaixo são do Brasil, pessoas elegíveis (n = 2.234).

## 1. Recusa na 1ª resposta

- **Onde olha:** só os 300 primeiros caracteres da 1ª resposta do assistente, em minúsculas.
- **Regra:** marca recusa se aparece qualquer uma destas expressões: `desculp`, `sinto muito`, `lamento`, `não posso`, `não sou capaz`, `não tenho como`, `modelo de linguagem`, `como um(a) IA`, `I'm sorry`, `I am sorry`, `I apologize`, `I cannot`, `I can't`, `I'm unable`, `as an AI`, `as a language model`.
- **Quanto a regra marca:** 198 das 2.234 pessoas elegíveis (8,9%); em conversas, 911 de 11.621 (7,8%).
- **Como ler:** "**recusa ou ressalva de IA**", não "recusa estrita". Não medimos quantas recusas a regra deixa passar.
- **Como estreitar:** tirar `as an ai` e `modelo de linguagem` soltos da regra, ou classificar em lote com um LLM na AWS e conferir contra a mesma amostra.

## 2. Tema do 1º pedido

- **Onde olha:** os 600 primeiros caracteres do 1º pedido, em minúsculas.
- **Como decide:** 11 temas testados **em ordem**; **a primeira regra que bate vence**. Por isso um pedido de ficção adulta vira "Adulto/sensível", e não "Ficção".

| # | Tema | Regra (resumo) | Pessoas | % |
|---|---|---|---|---|
| 1 | Vazio | pedido em branco | 69 | 3,1 |
| 2 | Saudação | até 30 caracteres começando com oi, olá, hello, bom dia, tudo bem… | 386 | 17,3 |
| 3 | Prompt de imagem | midjourney, stable diffusion, dall-e, prompt generator | 15 | 0,7 |
| 4 | Persona/roleplay | "a partir de agora", "atue como", "act as", "you are a", jailbreak… | 90 | 4,0 |
| 5 | Adulto/sensível | palavras de sexo e erotismo | 21 | 0,9 |
| 6 | Tecnologia/código | python, javascript, sql, código, erro, excel, linux, github… | 218 | 9,8 |
| 7 | Tarefa escolar/acadêmica | questão, alternativa, exercício, equação, tcc, artigo, escola… | 99 | 4,4 |
| 8 | Escrita/edição/tradução | reescreva, corrija, resuma, traduza, e-mail, legenda, texto… | 244 | 10,9 |
| 9 | Ficção/criação | história, conto, poema, letra, personagem, roteiro… | 123 | 5,5 |
| 10 | Conhecimento/pergunta | o que, como, qual, quem, por que, explique, defina… | 531 | 23,8 |
| 11 | Outro | nenhuma regra bateu | 438 | 19,6 |

- **Precisão:** **não foi medida**. Palavras amplas ("texto", "programa", "aula") geram falsos positivos; temas pequenos têm margem de erro grande. Decisão e alternativas (LLM no Bedrock, embeddings) em [`BDR-003`](bdr/BDR-003-classificacao-de-tema.md).
- **Como estreitar:** conferir uma amostra por tema, corrigir as regras e remedir.

## 3. Idioma do pedido x idioma do navegador

- **Idioma do pedido:** já vem na base (campo `language`, detectado pelos autores do WildChat, **não por nós**).
- **Idioma do navegador:** a **primeira etiqueta** do cabeçalho `Accept-Language` da requisição (por exemplo `pt-BR`), em minúsculas. Comparamos só a parte antes do hífen (`pt`). Fica em `silver.fato_usuario.idioma_navegador`.
- **Comparação:** o idioma do pedido é traduzido para o código de 2 letras (19 idiomas: inglês, português, espanhol, francês, alemão, russo, chinês, japonês, coreano, árabe, italiano, turco, holandês, polonês, indonésio, vietnamita, persa, ucraniano, tailandês). Se bate com o do navegador, o pedido está "no idioma do navegador".

| Grupo | Pessoas | Retorno em 7 dias |
|---|---|---|
| Pedido no idioma do navegador | 1.560 | 24,5% |
| Inglês, com navegador em outro idioma | 317 | 25,9% |
| Outro idioma (nem o do navegador, nem inglês) | 343 | 18,4% |

- **Fora da conta:** 14 pessoas sem o cabeçalho. Idiomas fora da lista de 19 (como "Nolang" ou finlandês) caem em "outro idioma".
- **Limite:** é um recorte descritivo, sem ajuste; o navegador em português não garante que a pessoa seja brasileira, e o primeiro idioma do cabeçalho é só uma indicação.

## Conferir em SQL

```sql
-- recusa: pessoas elegíveis do Brasil com recusa na 1ª resposta
SELECT count(*) FILTER (WHERE recusa) AS com_recusa, count(*) AS elegiveis
FROM silver.fato_usuario WHERE pais = 'Brazil' AND elegivel;

-- tema: pessoas por tema
SELECT t.tema, count(*) AS pessoas
FROM silver.fato_usuario u JOIN silver.dim_tema t USING (tema_id)
WHERE u.pais = 'Brazil' AND u.elegivel GROUP BY 1 ORDER BY 2 DESC;

-- idioma x navegador: pessoas e retorno por grupo
SELECT nivel, elegiveis, voltaram_7d
FROM gold.agg_retorno_fator WHERE pais = 'Brazil' AND fator = 'idioma_x_navegador' ORDER BY 1;
```