"""Auditoria da GOLD: completa o funil por pais (auditoria.fluxo_pais) com o que a gold tem (gold_usuarios e gold_conversas).
A silver ja gravou o resto do funil (camadas/silver/auditoria.py); a gold so existe depois, por isso este passo vem depois dela."""

SQL_FUNIL_GOLD = """
UPDATE auditoria.fluxo_pais f SET gold_usuarios = g.usuarios, gold_conversas = g.conversas
FROM gold.pais g WHERE f.execucao_id = %(e)s AND f.pais = g.pais
"""

SQL_FUNIL_GOLD_TOTAL = """
UPDATE auditoria.fluxo_pais t SET gold_usuarios = s.u, gold_conversas = s.c
FROM (SELECT sum(gold_usuarios) AS u, sum(gold_conversas) AS c FROM auditoria.fluxo_pais
      WHERE execucao_id = %(e)s AND pais <> '(todos)') s
WHERE t.execucao_id = %(e)s AND t.pais = '(todos)'
"""


def auditar_gold(dw, exec_id: int) -> None:
    with dw.cursor() as cur:
        cur.execute(SQL_FUNIL_GOLD, {"e": exec_id})
        cur.execute(SQL_FUNIL_GOLD_TOTAL, {"e": exec_id})
