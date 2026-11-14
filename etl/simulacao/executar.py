"""Roda UMA carga do ETL com um defeito plantado, para provar que o detector de anomalia aponta a camada certa.
Uso (feito pelo orquestrador, simulacao/cenarios.py):  python -m simulacao.executar <cenario>
Os defeitos entram DEPOIS de a camada ser construida, como se o codigo dela tivesse errado:
  silver, transformacao   70-80% dos retornantes nao entram como elegiveis (a regra de elegibilidade erra); a gold e construida em cima desse erro
  gold                    a agregacao da gold triplica os que voltaram no Brasil; a silver esta certa
  base, bronze            nenhum defeito no codigo (o da bronze esta na semente)
"""
import sys

from camadas import gold, silver

ERRO_ELEGIBILIDADE = """UPDATE silver.fato_usuario SET elegivel = false
                        WHERE pais = 'Brazil' AND elegivel AND NOT voltou_7d AND abs(hashtext(usuario_id)) % 10 < 8"""


def plantar(cenario: str) -> None:
    if cenario in ("silver", "transformacao"):
        original = silver.construir_silver

        def silver_com_defeito(dw):
            r = original(dw)
            dw.execute(ERRO_ELEGIBILIDADE)
            return r
        silver.construir_silver = silver_com_defeito
    elif cenario == "gold":
        original = gold.construir_gold

        def gold_com_defeito(dw):
            r = original(dw)
            dw.execute("UPDATE gold.pais SET voltaram_7d = voltaram_7d * 3 WHERE pais = 'Brazil'")
            return r
        gold.construir_gold = gold_com_defeito


if __name__ == "__main__":
    plantar(sys.argv[1])
    import main
    sys.exit(main.main())
