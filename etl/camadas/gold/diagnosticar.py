"""Diagnostico da GOLD: linhas e "impressao digital" do conteudo de cada tabela, mais os numeros de negocio que a tela mostra.
Se a mesma semente gerar uma impressao diferente da carga anterior, algo mudou (uma regra, um parametro ou o proprio codigo).
Para investigar: SELECT * FROM auditoria.mudancas_entre_cargas WHERE camada = 'gold';"""
from comum.diagnostico import Metrica, coletar

TABELAS = ["gold.pais", "gold.agg_retorno_semana", "gold.agg_retorno_fator", "gold.agg_uso_dia", "gold.agg_retorno_mes_fator",
           "gold.problema_qualidade", "gold.agg_curva_retorno", "gold.agg_estrato", "gold.agg_recusa_modelo", "gold.agg_concentracao",
           "gold.agg_uso_hora", "gold.agg_modelo_mes", "gold.efeito_fator", "gold.catalogo_indicador"]

_LINHAS = " UNION ALL ".join(f"SELECT '{t}', count(*), NULL FROM {t}" for t in TABELAS)
_IMPRESSAO = " UNION ALL ".join(f"SELECT '{t}', NULL, coalesce(sum(hashtextextended(x::text, 0)::numeric), 0)::text FROM {t} x" for t in TABELAS)

CONSULTAS = [
    ("linhas", _LINHAS),
    ("impressao", _IMPRESSAO),
    ("brasil_elegiveis", "SELECT NULL, usuarios_elegiveis, NULL FROM gold.pais WHERE pais = 'Brazil'"),
    ("brasil_voltaram_7d", "SELECT NULL, voltaram_7d, NULL FROM gold.pais WHERE pais = 'Brazil'"),
    ("brasil_retorno_7d", "SELECT NULL, round(voltaram_7d::numeric / usuarios_elegiveis, 6), NULL FROM gold.pais WHERE pais = 'Brazil'"),
    ("efeitos_brasil", "SELECT contraste, efeito_pp, NULL FROM gold.efeito_fator WHERE pais = 'Brazil'"),
]


def diagnosticar_gold(dw) -> list[Metrica]:
    return coletar(dw, "gold", CONSULTAS)
