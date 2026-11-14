"""GOLD: executa os comandos do gold/sql.py na ordem certa (silver -> gold). Roda DENTRO da transacao de carga.
Cada tabela da gold responde a uma pergunta da tela; o catalogo de indicadores vem de comum/definicoes.py (CATALOGO).
Taxa e margem de erro (Wilson, 95%) so aparecem com 30 ou mais pessoas."""
from comum.definicoes import CATALOGO

from .limpar import limpar_gold
from .sql import (SQL_CONCENTRACAO, SQL_CONCENTRACAO_PAIS, SQL_CURVA, SQL_ESTRATO, SQL_MODELO_MES, SQL_PAIS, SQL_PROBLEMAS, SQL_RECUSA_MODELO, SQL_RETORNO_FATOR, SQL_RETORNO_MES_FATOR, SQL_RETORNO_SEMANA, SQL_RETORNO_SEM_TOP10, SQL_USO_DIA, SQL_USO_HORA)


def construir_gold(dw) -> None:
    """Dentro da transacao `dw`."""
    limpar_gold(dw)
    with dw.cursor() as cur:
        cur.execute(SQL_PAIS)
        cur.execute(SQL_RETORNO_SEMANA)
        cur.execute(SQL_RETORNO_FATOR)
        cur.execute(SQL_USO_DIA)
        cur.execute(SQL_RETORNO_MES_FATOR)
        cur.execute(SQL_PROBLEMAS)
        for sql in (SQL_CURVA, SQL_ESTRATO, SQL_RECUSA_MODELO, SQL_CONCENTRACAO, SQL_CONCENTRACAO_PAIS, SQL_RETORNO_SEM_TOP10, SQL_USO_HORA, SQL_MODELO_MES):
            cur.execute(sql)
        cur.executemany(
            """INSERT INTO gold.catalogo_indicador (indicador_id, nome, pergunta, unidade, denominador, formula,
               sql_referencia, fonte, periodo_referencia, amostra_minima)
               VALUES (%(indicador_id)s, %(nome)s, %(pergunta)s, %(unidade)s, %(denominador)s, %(formula)s,
                       %(sql_referencia)s, %(fonte)s, %(periodo_referencia)s, %(amostra_minima)s)""", CATALOGO)
