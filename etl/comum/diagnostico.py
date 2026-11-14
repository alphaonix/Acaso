"""Diagnostico por camada: medidas que descrevem o estado da camada depois de construida (contagens, vazios, distribuicoes e
"impressoes digitais" do conteudo). Servem a dois fins: INVESTIGAR (consultar o historico quando um numero parecer errado) e
PREVENIR (comparar com a carga anterior, ver comum/deriva.py). Fica gravado em auditoria.metrica, uma linha por medida e por carga.

Cada camada tem o seu `diagnosticar.py` com a lista de consultas. Uma consulta devolve linhas (escopo, valor, texto):
  escopo  a que se refere (pais, tabela, coluna...), ou vazio     valor  numero (ou nulo)     texto  impressao digital (ou nulo)
"""
from dataclasses import dataclass


@dataclass
class Metrica:
    camada: str
    nome: str
    escopo: str = ""
    valor: float | None = None
    texto: str | None = None


def coletar(dw, camada: str, consultas: list[tuple[str, str]]) -> list[Metrica]:
    """Roda cada (nome, sql) na transacao da carga e transforma as linhas devolvidas em metricas."""
    saida = []
    with dw.cursor() as cur:
        for nome, sql in consultas:
            for escopo, valor, texto in cur.execute(sql).fetchall():
                saida.append(Metrica(camada, nome, "" if escopo is None else str(escopo), None if valor is None else float(valor), texto))
    return saida


def gravar_metricas(ops, execucao_id: int, metricas: list[Metrica]) -> None:
    """Grava pela conexao automatica (`ops`): o historico fica mesmo se a carga for desfeita, o que ajuda a investigar a falha."""
    with ops.cursor() as cur:
        cur.executemany(
            """INSERT INTO auditoria.metrica (execucao_id, camada, metrica, escopo, valor, texto) VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            [(execucao_id, m.camada, m.nome, m.escopo, m.valor, m.texto) for m in metricas])
