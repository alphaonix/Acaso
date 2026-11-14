"""Diagnostico da SILVER: contagens por pais, vazios, distribuicao dos temas e das combinacoes de navegador, e "impressoes digitais"
do conteudo (soma de hashes das linhas: se uma unica pessoa ou conversa mudar, a impressao muda).
Para investigar: SELECT * FROM auditoria.historico_metrica WHERE camada = 'silver' ORDER BY execucao_id DESC;"""
from comum.diagnostico import Metrica, coletar

_VAZIOS_CONVERSA = ["estado", "idioma", "modelo", "tema_id", "recusa", "prompt1_chars", "resp1_chars"]
_VAZIOS_USUARIO = ["estado", "idioma", "navegador", "sistema", "tema_id", "recusa", "idioma_navegador"]


def _nulos(tabela: str, colunas: list[str]) -> str:
    return " UNION ALL ".join(f"SELECT '{c}', count(*) FILTER (WHERE {c} IS NULL), NULL FROM {tabela}" for c in colunas)


CONSULTAS = [
    ("conversas", "SELECT pais, count(*), NULL FROM silver.fato_conversa GROUP BY pais"),
    ("pessoas", "SELECT pais, count(*), NULL FROM silver.fato_usuario GROUP BY pais"),
    ("pessoas_elegiveis", "SELECT pais, count(*) FILTER (WHERE elegivel), NULL FROM silver.fato_usuario GROUP BY pais"),
    ("voltaram_7d", "SELECT pais, count(*) FILTER (WHERE elegivel AND voltou_7d), NULL FROM silver.fato_usuario GROUP BY pais"),
    ("voltaram_24h", "SELECT pais, count(*) FILTER (WHERE elegivel AND voltou_24h), NULL FROM silver.fato_usuario GROUP BY pais"),
    ("nulos_conversa", _nulos("silver.fato_conversa", _VAZIOS_CONVERSA)),
    ("nulos_pessoa", _nulos("silver.fato_usuario", _VAZIOS_USUARIO)),
    ("tema_brasil", "SELECT t.tema, count(*), NULL FROM silver.fato_usuario u JOIN silver.dim_tema t USING (tema_id) WHERE u.pais = 'Brazil' GROUP BY 1"),
    ("pessoas_por_navegador_sistema", "SELECT navegador || '/' || sistema, count(*), NULL FROM silver.fato_usuario GROUP BY 1"),
    ("impressao_pessoas", """SELECT NULL, NULL, sum(hashtextextended(usuario_id || '|' || pais || '|' || voltou_7d::int || voltou_24h::int || elegivel::int
                                  || '|' || convs_total || '|' || primeira_vez_utc::text || '|' || coalesce(modelo, ''), 0)::numeric)::text
                            FROM silver.fato_usuario"""),
    ("impressao_conversas", """SELECT NULL, NULL, sum(hashtextextended(conversation_hash || '|' || usuario_id || '|' || inicio_utc::text || '|' || fim_utc::text
                                  || '|' || modelo || '|' || coalesce(recusa::text, '') || '|' || coalesce(tema_id::text, ''), 0)::numeric)::text
                            FROM silver.fato_conversa"""),
]


def diagnosticar_silver(dw) -> list[Metrica]:
    return coletar(dw, "silver", CONSULTAS)
