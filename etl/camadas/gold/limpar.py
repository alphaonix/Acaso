"""Esvazia a GOLD antes de reconstrui-la (dentro da transacao: se a carga falhar, os dados antigos voltam)."""


def limpar_gold(dw) -> None:
    with dw.cursor() as cur:
        cur.execute("""TRUNCATE gold.pais, gold.agg_retorno_semana, gold.agg_retorno_fator, gold.agg_uso_dia, gold.agg_retorno_mes_fator,
                       gold.problema_qualidade, gold.agg_curva_retorno, gold.agg_estrato, gold.agg_recusa_modelo, gold.agg_concentracao,
                       gold.agg_uso_hora, gold.agg_modelo_mes, gold.efeito_fator, gold.catalogo_indicador RESTART IDENTITY""")
