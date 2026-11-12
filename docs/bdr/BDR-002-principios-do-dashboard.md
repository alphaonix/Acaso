# BDR-002: princípios do dashboard (transparência, onboarding e filtro de país)

Status: aceita. Origem: conferência no Power BI (cartões que pareciam divergir por unidade/denominador distintos) e
critério do PDF: "cada tela se explica sozinha: cada número com definição e fonte, cada efeito com sua incerteza".

## Decisões

### 1. Todo cálculo tem a fórmula descrita
Cada indicador exibe (no tooltip "i" e na página de glossário) e no código:
- **Nome e pergunta que responde**, em linguagem de negócio.
- **Unidade** (usuário, conversa ou sessão) e **denominador** explícitos.
- **Fórmula** em texto e a **consulta SQL** correspondente.
- **Período de referência**, fuso (America/Sao_Paulo por padrão) e **fonte** (tabela da base analítica).
- **Incerteza** (intervalo de confiança de 95%) quando for taxa ou efeito.
- **Regra de amostra pequena:** abaixo de um mínimo de usuários, mostra "amostra pequena demais" em vez do número.

Exemplo, retorno em 7 dias: usuários elegíveis cuja primeira sessão tem uma sessão posterior iniciada em até 7 dias
÷ usuários elegíveis; elegível = primeira vez ≥ 30 dias após o início dos dados e ≥ 7 dias antes do fim. Fonte:
`usuarios`. IC de Wilson 95%.

### 2. Tela de abertura (onboarding) antes de qualquer gráfico
Uma página curta, lida antes de acessar o painel, com:
- **Papel do dashboard** em 2 ou 3 frases (entender o que faz quem experimenta o assistente voltar em até 7 dias).
- **Resumo de cada indicador** em uma linha (o que mede, unidade, como ler).
- **O que o dashboard nunca mostra** (texto de conversas, IP, identificadores individuais) e como a privacidade é tratada.
- Aviso de que o resultado é associação, não prova de causa, e o que a análise causal faz para reduzir a seleção.
- Botão "Entendi, abrir o painel" (e link permanente "Como ler" no cabeçalho).
Cada tela também tem uma frase de topo com a pergunta que responde.

### 3. Filtro de país global
Seletor de país no cabeçalho, presente em todas as telas e em todos os endpoints (`?pais=`). Padrão: Brasil.
- A base analítica guarda todos os países, com `pais` e fuso em todas as tabelas (a base bruta de 837.989 conversas
  já é carregada inteira).
- O fuso do dia e da semana vem de `dim_pais`; o idioma da interface é escolhido à parte do país.
- Países com poucos usuários mostram o aviso de amostra pequena. Variáveis que dependem do texto (tema, recusa) podem
  não estar disponíveis para todos os países; a tela mostra "indisponível" e explica o motivo (a classificação em
  profundidade é feita só para o Brasil; a decisão de custo entra em um ADR próprio).
- Comparação entre países usa a mesma definição de retorno e mostra o intervalo de confiança de cada um.

## Consequências
- Mais trabalho de texto e de metadados por indicador, compensado por um catálogo único (arquivo de definições) que
  alimenta tooltip, glossário, onboarding, README e testes. Uma definição muda em um só lugar.
- O teste automatizado compara a fórmula descrita com a consulta executada para que a definição não mude sem aviso.
