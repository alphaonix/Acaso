"""Roda UMA carga do ETL com um defeito plantado, para provar que o detector de anomalia aponta a camada certa.
Uso (feito pelo orquestrador, simulacao/cenarios.py):  python -m simulacao.executar <cenario>

Os defeitos de CODIGO entram DEPOIS de a camada ser construida, como se o codigo dela tivesse errado. Os defeitos da BRONZE estao na semente
(simulacao/gerar_semente.py). No fim, a carga de um cenario e DESFEITA (rollback): a anomalia ja ficou registrada em auditoria.anomalia, e a carga
normal continua sendo a referencia do proximo cenario (nao precisa recarregar tudo a cada vez).
"""
import os
import sys

from camadas import gold, silver
from comum import anomalia_semanal

SILVER_ELEGIBILIDADE = """UPDATE silver.fato_usuario SET elegivel = false
                          WHERE pais = 'Brazil' AND elegivel AND NOT voltou_7d AND abs(hashtext(usuario_id)) % 10 < 8"""
SILVER_RETORNO = """UPDATE silver.fato_usuario SET voltou_7d = true
                    WHERE pais = 'Brazil' AND elegivel AND NOT voltou_7d AND abs(hashtext(usuario_id)) % 10 < 3"""
SILVER_LIMPEZA = "DELETE FROM silver.fato_conversa WHERE pais = 'Brazil' AND abs(hashtext(conversation_hash)) % 10 < 5"
def _ua_bruto_na_pessoa() -> None:
    """Reintroduz o erro do incidente do PDF (4.2): a pessoa passa a ser hash(endereco + user-agent BRUTO), com a versao do navegador."""
    from camadas.silver import construir
    from comum.definicoes import UA_NORM_SQL
    assert UA_NORM_SQL in construir.SQL_CONV
    construir.SQL_CONV = construir.SQL_CONV.replace(UA_NORM_SQL, "coalesce(c.ua, '')")


GOLD_NUMERADOR ="UPDATE gold.pais SET voltaram_7d = voltaram_7d * 3 WHERE pais = 'Brazil'"
GOLD_DENOMINADOR = "UPDATE gold.pais SET usuarios_elegiveis = usuarios_elegiveis / 2 WHERE pais = 'Brazil'"
GOLD_TROCADO = """UPDATE gold.pais b SET usuarios_elegiveis = o.usuarios_elegiveis, voltaram_7d = o.voltaram_7d
                  FROM (SELECT usuarios_elegiveis, voltaram_7d FROM gold.pais WHERE pais <> 'Brazil' ORDER BY usuarios_elegiveis DESC LIMIT 1) o
                  WHERE b.pais = 'Brazil'"""

DEFEITOS = {"silver_elegibilidade": ("silver", SILVER_ELEGIBILIDADE), "codigo_mudou": ("silver", SILVER_ELEGIBILIDADE),
            "silver_retorno_inflado": ("silver", SILVER_RETORNO), "silver_limpeza_exagerada": ("silver", SILVER_LIMPEZA),
            "incidente_navegador": ("silver", None),           # defeito no CODIGO da regra de pessoa (sem SQL depois): ver _ua_bruto_na_pessoa
            "gold_numerador": ("gold", GOLD_NUMERADOR), "gold_denominador": ("gold", GOLD_DENOMINADOR), "gold_pais_trocado": ("gold", GOLD_TROCADO)}


def plantar(cenario: str) -> None:
    if cenario == "incidente_navegador":
        _ua_bruto_na_pessoa()
    if cenario in DEFEITOS and DEFEITOS[cenario][1]:
        camada, sql = DEFEITOS[cenario]
        modulo, nome = (silver, "construir_silver") if camada == "silver" else (gold, "construir_gold")
        original = getattr(modulo, nome)

        def com_defeito(dw):
            r = original(dw)
            dw.execute(sql)
            return r
        setattr(modulo, nome, com_defeito)
    if cenario != "base":
        import main
        verificar = anomalia_semanal.verificar        # e a ultima verificacao da carga: o que ela e a anterior gravaram ja esta em auditoria.*

        def verificar_e_desfazer(ops, dw, exec_id):
            verificar(ops, dw, exec_id)
            raise main.PortaoFalhou("simulacao: carga desfeita de proposito (o resultado ficou em auditoria.anomalia e auditoria.anomalia_semanal)")
        anomalia_semanal.verificar = verificar_e_desfazer


if __name__ == "__main__":
    os.environ["ETL_APROVAR_ANOMALIAS"] = "1"      # a simulacao precisa ir ate o fim (as duas verificacoes); ela mesma desfaz a carga no final
    plantar(sys.argv[1])
    import main
    sys.exit(main.main())
