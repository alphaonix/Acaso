# BDR-001: pessoa, sessão, primeira experiência e retorno

Status: aceita (premissa de trabalho). Brasil: 11.621 conversas, 2.385 endereços, 09/04/2023 a 29/04/2024.

## Contexto
A base não tem ID de usuário, e o enunciado (2.3) permite assumir definições se o impacto de errar for registrado. O que condiciona a escolha:
- O `timestamp` do topo é o horário da **última** resposta do assistente (UTC). As mensagens da pessoa têm horário vazio em todas as 837.989 conversas; só as do assistente têm horário.
- Uma conversa pode durar horas (p99 de 5,8 h).
- `conversation_hash` repetido não é duplicata: os 27 hashes repetidos do Brasil têm IP e horário diferentes.
- Uso concentrado: 1 endereço tem 1.557 conversas, os 10 maiores somam 32,5%, e 59,7% dos endereços têm uma conversa só.
- 1.060 conversas (0,13%) não têm país e ficam como "Desconhecido".

## Opções
1. **Pessoa = endereço (`hashed_ip`).** Junta quem divide a mesma rede (celular, escola) e separa quem troca de rede.
2. **Endereço + navegador completo, com a versão.** Conta a mesma pessoa várias vezes quando o navegador atualiza (a causa do incidente da seção 4.2).
3. **Endereço + família do navegador e do sistema, sem versão.**

## Decisão
- **Pessoa:** opção 3. As opções 1 e 2 entram como sensibilidade.
- **Sessão:** uma conversa com mais de **30 min** de intervalo depois do fim da anterior abre nova sessão.
- **Primeira experiência:** a primeira sessão da pessoa no período.
- **Início da conversa:** o horário da primeira resposta do assistente (`primeira_resposta_ts`), igual para todos os países e calculado ao gerar a semente. Fica alguns segundos depois de a pessoa escrever; como o retorno é medido em dias, isso não muda o resultado.
- **Retorno em 7 dias:** existe outra sessão que começa em até 7 dias (168 h) depois do início da primeira. Compara instantes, então não depende do fuso.
- **Elegível:** a primeira vez é pelo menos 30 dias depois do início dos dados (evita contar antigos como novos) e pelo menos 7 dias antes do fim (a janela tem de estar completa).
- **Duplicata exata:** mesma conversa (hash), endereço e início. São 17 linhas, nenhuma do Brasil, 0,002% da base; ficam em `auditoria.registro_excluido`. O mesmo hash com início diferente é outra conversa.

Resultado: **23,7% de retorno em 7 dias**, 530 de 2.234 pessoas elegíveis (2.530 no total).

## Impacto se a premissa estiver errada (medido)
Tabela completa em `docs/SENSIBILIDADE.md` (`python analise/05_sensibilidade_definicoes.py`). Incerteza estatística da definição adotada: ±1,8 pp.

| Premissa | Variante | Retorno |
|---|---|---|
| Adotada | endereço + navegador e sistema, 30 min, janela de 7 dias | 23,7% |
| Pessoa | só o endereço | 23,7% |
| Pessoa | endereço + navegador completo | 26,2% |
| Sessão | 15 min / 60 min / 120 min | 26,3% / 21,3% / 19,6% |
| Janela | 3 dias / 14 dias (outro indicador, não um erro) | 20,8% / 25,3% |
| Aquecimento | 0 / 15 / 60 dias (em vez de 30) | 24,1% / 23,9% / 23,9% |

O **gap da sessão** é a premissa que mais pesa (6,8 pp): o número deve ser lido como "retorno com sessões de 30 min". A definição de pessoa move até 2,5 pp, e o aquecimento, menos de 0,4 pp.

## Limitação: "pessoa" é um navegador numa rede
Os vieses têm sentidos opostos e a direção líquida não é conhecida:

| Caso | Efeito no retorno |
|---|---|
| Mesma pessoa em celular e PC | Subestima (volta por outro aparelho e conta como nova) |
| Mesma pessoa em Wi-Fi e 4G | Subestima |
| Várias pessoas no mesmo endereço e navegador (escola, escritório) | Superestima |

Falta um identificador de usuário (login ou cookie); é uma pergunta aberta para o cliente (`docs/RISCOS.md`).
