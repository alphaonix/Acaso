"""Peças comuns do portao de qualidade: o resultado de uma conferencia, como executar uma lista delas e como gravar.
As conferencias em si ficam em cada camada (camadas/<camada>/validar.py). Elas comparam a carga com LEIS DE CONSERVACAO
(ex.: bronze = silver + excluidas) e com numeros VALIDADOS por conferencia independente (docs/VALIDACAO.md)."""
from dataclasses import dataclass


@dataclass
class Resultado:
    transicao: str     # grupo da conferencia (bronze_arquivos, bronze_silver, silver_interna, silver_gold, efeitos, validados)
    verificacao: str
    esperado: str
    obtido: str
    passou: bool


def executar(dw, verificacoes: list[tuple], execucao_id: int) -> list[Resultado]:
    """Roda cada (grupo, descricao, esperado, sql) e compara o valor unico devolvido com o esperado.
    Em vez do SQL pode vir uma funcao `f(dw)` que devolve o valor (usado pelo recalculo independente, feito em Python)."""
    resultados = []
    with dw.cursor() as cur:
        for transicao, descricao, esperado, sql in verificacoes:
            if callable(sql):
                obtido = str(sql(dw))
            else:
                cur.execute(sql, {"exec": execucao_id})
                obtido = str(cur.fetchone()[0])
            resultados.append(Resultado(transicao, descricao, esperado, obtido, obtido == esperado))
    return resultados


def gravar(ops, execucao_id: int, resultados: list[Resultado]) -> None:
    """Grava o resultado em ops.qa_resultado (conexao automatica: o historico fica mesmo se a carga falhar)."""
    with ops.cursor() as cur:
        cur.executemany(
            "INSERT INTO ops.qa_resultado (execucao_id, transicao, verificacao, esperado, obtido, passou) VALUES (%s, %s, %s, %s, %s, %s)",
            [(execucao_id, r.transicao, r.verificacao, r.esperado, r.obtido, r.passou) for r in resultados])
