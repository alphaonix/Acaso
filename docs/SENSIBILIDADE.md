# Sensibilidade das definições: quanto o retorno do Brasil muda se uma premissa estiver errada

Gerado por `analise/05_sensibilidade_definicoes.py` (reproduzível: com o `docker compose up` ativo, rode o script). Cada linha refaz o indicador direto da bronze mudando **uma** premissa por vez; a primeira linha é a definição adotada e **bate com o dashboard** (2.234 elegíveis, 530 voltaram, 23,7%).

Leitura: a incerteza estatística da definição adotada é de **±1,8 pp** (IC 95%). Uma variante que muda o retorno por menos que isso não altera a conclusão; mais que isso, **muda a leitura do número**.

| Premissa | Variante | Usuários | Elegíveis | Voltaram | Retorno (IC 95%) | Diferença | Leitura |
|---|---|---:|---:|---:|---|---:|---|
| Referência | Definição adotada (IP + navegador/sistema, sessão de 30 min, janela de 7 dias) | 2.530 | 2.234 | 530 | 23,7% (22,0% a 25,5%) | - | referência |
| Quem é o usuário | Só o IP | 2.385 | 2.109 | 499 | 23,7% (21,9% a 25,5%) | −0,1 pp | dentro da incerteza |
| Quem é o usuário | IP + user-agent completo (com a versão do navegador) | 2.895 | 2.565 | 673 | 26,2% (24,6% a 28,0%) | +2,5 pp | **muda a leitura** |
| Gap da sessão | 15 minutos | 2.530 | 2.234 | 588 | 26,3% (24,5% a 28,2%) | +2,6 pp | **muda a leitura** |
| Gap da sessão | 60 minutos | 2.530 | 2.234 | 476 | 21,3% (19,7% a 23,1%) | −2,4 pp | **muda a leitura** |
| Gap da sessão | 120 minutos | 2.530 | 2.234 | 437 | 19,6% (18,0% a 21,3%) | −4,2 pp | **muda a leitura** |
| Período de lavagem | 14 dias | 2.530 | 2.410 | 576 | 23,9% (22,2% a 25,6%) | +0,2 pp | dentro da incerteza |
| Período de lavagem | 60 dias | 2.530 | 1.874 | 447 | 23,9% (22,0% a 25,8%) | +0,1 pp | dentro da incerteza |
| Janela de retorno | 3 dias | 2.530 | 2.259 | 470 | 20,8% (19,2% a 22,5%) | −2,9 pp | **muda a leitura** |
| Janela de retorno | 14 dias | 2.530 | 2.181 | 552 | 25,3% (23,5% a 27,2%) | +1,6 pp | dentro da incerteza |
| Início da conversa | Horário do último turno (campo timestamp) | 2.530 | 2.235 | 555 | 24,8% (23,1% a 26,7%) | +1,1 pp | dentro da incerteza |
| Regra de retorno | Qualquer conversa 1 h depois da primeira (sem sessão; regra do incidente) | 2.530 | 2.234 | 515 | 23,1% (21,4% a 24,8%) | −0,7 pp | dentro da incerteza |
| Usuários extremos | Sem o usuário mais ativo | 2.529 | 2.234 | 530 | 23,7% (22,0% a 25,5%) | +0,0 pp | dentro da incerteza |
| Usuários extremos | Sem os 10 usuários mais ativos | 2.520 | 2.225 | 522 | 23,5% (21,7% a 25,3%) | −0,3 pp | dentro da incerteza |

## Quais premissas mais mexem no número

Faixa do retorno ao variar cada premissa (a adotada incluída), da mais para a menos sensível:

- **Gap da sessão:** de 19,6% a 26,3% (amplitude de 6,8 pp)
- **Janela de retorno:** de 20,8% a 25,3% (amplitude de 4,5 pp)
- **Quem é o usuário:** de 23,7% a 26,2% (amplitude de 2,6 pp)
- **Início da conversa:** de 23,7% a 24,8% (amplitude de 1,1 pp)
- **Regra de retorno:** de 23,1% a 23,7% (amplitude de 0,7 pp)
- **Usuários extremos:** de 23,5% a 23,7% (amplitude de 0,3 pp)
- **Período de lavagem:** de 23,7% a 23,9% (amplitude de 0,2 pp)

## Como ler

- **Só o IP** junta quem divide a rede (celular, escola, CGNAT) e reduz o número de usuários; **user-agent completo** separa quem atualiza o navegador (é o defeito de código do incidente da seção 4.2). A definição adotada fica no meio: IP + família do navegador + sistema, sem versão.
- **Gap da sessão** e **lavagem** mudam quem conta como "voltou" e quem conta como "novo"; **janela** muda o que é "voltar" (é outro indicador, não um erro).
- **Horário do último turno** e a **regra de 1 h** são as armadilhas do código do incidente; estão aqui para mostrar quanto elas custariam.
- **Sem os usuários mais ativos** mostra se poucos usuários (como o IP com 1.557 conversas) puxam o número.

Limite: a amostra é pequena (cerca de 2,2 mil elegíveis), então diferenças menores que a incerteza acima não são distinguíveis de ruído.


## Fuso, período dos dados e janela de elegibilidade (medido em SQL)

Duas premissas de calendário que o script acima não varia; esta seção é escrita à mão, e o script não a gera. Consultas sobre `silver.fato_usuario` e `silver.fato_conversa`, Brasil; os dados vão de 09/04/2023 00:11 UTC a 29/04/2024 23:33 UTC.

**Fuso.** O retorno em 7 dias compara instantes (timestamps), então **não depende do fuso**. O fuso só escolhe a **semana, a hora e o dia da semana** de cada pessoa. Entre as 2.234 elegíveis, **42 (1,9%) mudariam de semana** se usássemos UTC no lugar de America/Sao_Paulo; a hora muda para todas, como esperado (diferença de 3 h). Efeito no número principal: nenhum; efeito nas telas de semana e de horário: pequeno, e o horário só é correto se o país tiver um único fuso (premissa registrada em `dim_pais`; para o Brasil, o estado vem na silver).

**Período de aquecimento (lavagem).** Quem aparece nos primeiros N dias dos dados pode ser um usuário antigo, não novo. Variando N com a mesma regra de janela completa no fim:

| Aquecimento (dias) | Elegíveis | Voltaram | Retorno |
|---|---|---|---|
| 0 | 2.479 | 597 | 24,08% |
| 15 | 2.405 | 575 | 23,91% |
| **30 (adotado)** | **2.234** | **530** | **23,72%** |
| 60 | 1.874 | 447 | 23,85% |

**Janela completa no fim.** Exigir 14 dias antes do fim dos dados, no lugar de 7, dá 2.181 elegíveis e 24,03%. Conclusão: as duas escolhas de calendário mexem **menos de 0,4 pp**, bem dentro do intervalo de Wilson (22,0% a 25,5%); o que mexe de verdade é o gap de sessão (tabela acima).