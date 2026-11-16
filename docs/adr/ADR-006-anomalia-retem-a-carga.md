# ADR-006: anomalia retém a carga até aprovação

Status: aceita (16/11/2026).

## Contexto
O PDF (4.2) descreve um número que mudou de forma abrupta (retorno de 31% para 18%) e foi publicado sem que ninguém percebesse. As conferências de conservação não pegam isso: o dado novo pode estar internamente consistente e mesmo assim errado.

## Opções
1. **Só alertar e publicar.** Simples, mas o número errado já chegou ao cliente.
2. **Derrubar a carga na anomalia.** Protege, mas impede publicar uma mudança real.
3. **Reter a carga até alguém aprovar.** O painel segue com os números anteriores e a decisão fica com quem opera.

## Decisão
Opção 3.
- O ETL compara cada carga com a anterior. Há anomalia quando a taxa de retorno em 7 dias de um país (30 ou mais elegíveis) muda 5 pontos percentuais ou mais com z de 4 ou mais, ou quando uma semana tem pico de novos, salto da taxa ou muitos "novos" com endereço já conhecido (`comum/anomalia.py` e `comum/anomalia_semanal.py`).
- **Anomalia retém a carga:** rollback, status `retida`, nada é publicado, e o painel e a API continuam com a carga anterior. O ETL termina com código 0.
- **Para publicar:** `docker compose run --rm etl python main.py --aprovar-anomalias`. A carga é refeita e publicada com o registro do que foi aprovado (status `alerta`). Se era defeito, corrija a causa e use `--recarregar`.
- Uma carga retida não se repete a cada `docker compose up`, a menos que a semente mude.
- A primeira carga de um banco vazio nunca é retida (não há com o que comparar).
- Deriva (números mudaram com a mesma semente) e integridade (alguém mexeu fora do ETL) só alertam. Falha de conservação cancela a carga (`falhou`).
- **Relatório em PDF** (`exports/relatorio_anomalia_carga_<id>.pdf`), **só quando há anomalia**: o que mudou, a camada provável (bronze, silver, gold ou código), o país ou a semana e uma amostra de pessoas por código anônimo.

## Consequências
- O detector só enxerga mudanças entre cargas e só os sinais do código. Mudança lenta ou um defeito que já existia na primeira carga passam.
- A simulação de 14 cenários (`docker compose --profile operacao run --rm simular-cenarios`) mostra que cada defeito plantado é apontado na camada certa. O PDF dela também só é gerado se algum cenário produzir anomalia.
- Na AWS, um alarme sobre o status `retida` avisaria o time (desenhado, não implementado).
