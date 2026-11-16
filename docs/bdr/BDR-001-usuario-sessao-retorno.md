# BDR-001: definição de usuário, sessão, primeira experiência e retorno

Status: aceita (premissa de trabalho). Números medidos por `analise/02_qualidade_definicoes.py` sobre o Brasil
(11.621 conversas, 2.385 IPs, 08/04/2023 a 29/04/2024).

## Contexto
A base não tem ID de usuário, e o enunciado (2.3) permite assumir definições, desde que registradas com o impacto de
estarem erradas. Achados de qualidade que condicionam a escolha:
- `timestamp` do topo = horário da última resposta do assistente (UTC).
- Mensagens do USUÁRIO têm timestamp nulo; só as do assistente têm horário. Logo o início da conversa não existe;
  usamos a **primeira resposta do assistente** como proxy de início (detalhe e como validar na seção
  "De onde vem o horário de início", ao fim deste documento).
- Conversas duram de 0 s (mediana, 1 troca) até ~5,8 h (p99): uma conversa pode se estender por horas.
- `conversation_hash` repetido: 27 hashes (93 linhas), TODOS com IP e horário diferentes. São conversas distintas com
  o mesmo texto, não duplicatas. Chave de deduplicação: (conversation_hash, hashed_ip, início).
- IP concentrado: 1 IP com 1.557 conversas; os 10 maiores somam 32,5% do volume; 59,7% dos IPs têm 1 conversa;
  11,3% dos IPs têm mais de 1 user-agent (máximo 35).
- País nulo: 1.060 conversas (0,13% das 837.989) não têm `country`; ficam como "Desconhecido" e fora da análise por país.
- Período: toxic = 0 em todo o Brasil (a base 1M já vem filtrada), 56 conversas redigidas, 51 sem estado.

## Opções consideradas
1. Usuário = `hashed_ip`. Une pessoas que dividem IP (CGNAT/celular) e separa quem troca de rede.
2. Usuário = `hashed_ip` + user-agent completo. Separa dispositivos, mas fragmenta a mesma pessoa quando o navegador
   atualiza a versão (é a causa do incidente da seção 4.2).
3. Usuário = `hashed_ip` + user-agent normalizado (família do navegador + sistema, sem versão).

## Decisão
- **Usuário (principal): opção 3.** Sensibilidade com 1 e 2.
- **Sessão:** novas conversas com intervalo maior que **30 min** após o fim da anterior iniciam nova sessão.
- **Primeira experiência:** primeira sessão do usuário no período (início = primeira resposta do assistente).
- **Retorno em 7 dias:** existe uma sessão posterior cujo início é ≤ 7 dias após o início da primeira. Janela em dias
  corridos no fuso America/Sao_Paulo.
- **Elegíveis:** usuários cuja primeira experiência ocorreu ≥ 30 dias após o início dos dados (reduz falsos "novos",
  censura à esquerda) e ≥ 7 dias antes do fim (censura à direita).

## Impacto se a premissa estiver errada (medido)
| Definição | Elegíveis | Retorno 7d (IC95) |
|---|---|---|
| IP, gap 30 min, lavagem 30 d | 2.109 | 23,7% [21,9; 25,5] |
| IP, gap 60 min | 2.109 | 21,3% [19,6; 23,1] |
| IP, gap 240 min | 2.109 | 17,6% [16,1; 19,3] |
| IP+UA completo, gap 30 min | 2.565 | 26,2% [24,6; 28,0] |
| IP+UA completo, gap 240 min | 2.565 | 19,6% [18,1; 21,2] |

- A regra de **sessão** (gap) move o retorno em até ~6 pontos; a regra de **usuário**, em até ~2,5 pontos; a lavagem de
  30 dias muda menos de 1 ponto. O nível absoluto do retorno é sensível; as comparações entre grupos devem ser
  reportadas sob a definição principal e conferidas sob as demais.
- Definição principal (opção 3, gap 30 min, lavagem 30 d), medida em `analise/03_exporta_powerbi.py`: **23,7%** de
  retorno em 7 dias, com 2.234 usuários elegíveis (2.530 usuários no total).

## Limitação: "usuário" aqui é um navegador em uma rede, não uma pessoa
A base não tem login nem cookie. O IP muda com a REDE (não com o dispositivo). Efeitos da chave IP + navegador/sistema:

| Cenário | O que a chave faz | Efeito no retorno |
|---|---|---|
| Mesma pessoa, celular e PC no mesmo Wi-Fi | Mesmo IP, navegadores diferentes: 2 usuários | Subestima (volta por outro aparelho conta como "novo") |
| Mesma pessoa, Wi-Fi em casa e 4G na rua | IPs diferentes: 2+ usuários | Subestima |
| Várias pessoas no mesmo IP e navegador (CGNAT, escola, escritório) | 1 usuário só | Superestima (atividade de um conta como retorno de outro) |

Os vieses têm sentidos opostos; a direção líquida não é conhecida só pela teoria.
- Mitigação: sensibilidade IP x IP+UA completo (diferença de ~2,5 pontos no retorno) e rodar com e sem o IP gigante.
- Dado que falta: identificador de usuário (login ou cookie). Entra em "o que os dados não permitem medir" e em
  "decisões em aberto" com o cliente (seção 4.3).
- Verificação sugerida: fração de IPs com mais de um navegador normalizado (referência: 11,3% dos IPs têm mais de um user-agent bruto).

## Próximos passos derivados
- Medir o efeito do IP gigante (1.557 conversas): rodar com e sem ele.
- Amostra pequena: ~2,1 mil usuários elegíveis; os intervalos serão largos para fatores raros, e a tela deve avisar.

## De onde vem o horário de início (e por que a mensagem do usuário não é usada)
**Fato:** na `conversation`, a mensagem 1 é do usuário e a mensagem 2 é a primeira resposta do assistente. O WildChat só
preenche horário nas mensagens do assistente. A mensagem 1 tem a chave `timestamp`, mas com valor vazio.

| | mensagem 1 (usuário) | mensagem 2 (assistente) |
|---|---|---|
| horário nas 11.621 conversas do Brasil | **0** | **11.621** |

**Conferido no arquivo bruto completo (`data/raw/wildchat_todos.parquet`, 837.989 conversas, todos os países):** a mensagem 1 tem
horário em **0** conversas e a mensagem 2 (assistente) em **todas** (Brasil 11.621; fora do Brasil 825.308; sem país 1.060). Não há
nenhuma mensagem de usuário com horário em toda a base. Então não é uma particularidade do Brasil.

**Regra do início (`inicio_utc`), igual para todos os países:** o início é `primeira_resposta_ts`, o horário da mensagem 2 (a 1ª
resposta do assistente). A coluna é calculada em um lugar só, ao gerar a semente (`make_seed.py`), do mesmo jeito para o arquivo
do Brasil e para o dos demais países, e vem preenchida nas 837.989 linhas da bronze. A silver só lê essa coluna.
- A mensagem 1 foi **examinada e descartada** porque é vazia em 100% das conversas (linha `msg_usuario_horario`, ação `ignorado`, na
  tabela `auditoria.nulos`). Não é uma segunda opção: é uma coluna sem dado.
- *Histórico (12/11):* antes disso, o arquivo do Brasil não trazia `primeira_resposta_ts` e a silver usava
  `coalesce(primeira_resposta_ts, conversation[2].timestamp)`. A unificação foi comparada antes e depois: `silver.fato_conversa` (837.972
  linhas), `silver.fato_usuario` (197.319) e as quatro tabelas gold que mudam com o início ficaram **idênticas**, e as conferências passam (hoje 66 por carga, ver README, seção 4).

**Impacto de usar a resposta do assistente:** o início fica alguns segundos depois do momento em que a pessoa escreveu. O retorno é
medido em dias, então não muda o resultado; a sessão (gap de 30 min) também não é afetada de forma relevante.

**Como validar (DBeaver):** `docs/CONFERIR_NUMEROS.md` e `docs/SENSIBILIDADE.md`.

## Duplicatas exatas (17 linhas, nenhuma do Brasil)
Uma linha é excluída se repete **hash da conversa + IP + início** de outra (fica a de menor `bronze_id`). Hash igual com início
diferente é outra conversa (a pessoa mandou o mesmo pedido de novo) e fica. Início tem precisão de segundos: duas conversas com o mesmo
hash e IP separadas por 1 s ficam as duas. Fora do Brasil o texto não está no banco, então a conclusão de "cópia" se apoia no hash
(calculado pelo WildChat sobre o conteúdo), no IP e no início, sem comparar o texto. Impacto: 17 de 837.989 linhas (0,002%),
nenhuma no Brasil; os números do desafio não mudam. A alternativa (manter todas as linhas) é aceitável pelo mesmo motivo. Cada
exclusão está em `auditoria.registro_excluido`, com a linha que ficou no lugar.

## Sensibilidade medida: o que muda se a premissa estiver errada
Tabela completa e reproduzível em `docs/SENSIBILIDADE.md` (`python analise/05_sensibilidade_definicoes.py`; a definição adotada bate com o dashboard). Resumo (retorno do Brasil: **23,7%, ±1,8 pp**):
- **Gap da sessão é a premissa que mais pesa:** 15 min → 26,3%; 60 min → 21,3%; 120 min → 19,6% (amplitude de 6,8 pp). Por isso o número deve ser lido como "retorno com sessões de 30 min".
- **Janela:** 3 dias → 20,8%; 14 dias → 25,3% (é outro indicador, não um erro).
- **Quem é o usuário:** só o IP dá os mesmos 23,7% (menos usuários: 2.385); com o user-agent **completo** (versão do navegador) dá 26,2% (+2,5 pp) e 2.895 "usuários": a fragmentação que causa o incidente da seção 4.2.
- **Sem efeito relevante:** lavagem (14 ou 60 dias: +0,1 a +0,2 pp), início = último turno (+1,1 pp), regra de 1 h sem sessão (−0,7 pp), retirar os 10 usuários mais ativos (−0,3 pp).
