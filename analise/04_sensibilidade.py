"""Sensibilidade dos efeitos (BDR-004): os achados mudam com a semente, o numero de dobras ou sem usuarios extremos?
Le o silver via Postgres local (docker compose up) e reutiliza etl/pipeline/estimar.py SEM gravar nada.
Uso:  python analise/04_sensibilidade.py
"""
import pathlib
import sys

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "etl"))
from pipeline import estimar as E  # noqa: E402

URL = "postgresql://etl:etl@localhost:5433/retencao"
FOCO = ["Recusa na primeira resposta", "Turnos da primeira conversa", "Tamanho do primeiro pedido", "Modelo",
        "Tamanho da primeira resposta", "Saudação"]
SQL0, SEMENTE0, K0 = E.SQL, E.SEMENTE, E.K_DOBRAS

VARIANTES = [
    ("base (semente 42, 5 dobras)", "", 42, 5),
    ("semente 7", "", 7, 5),
    ("semente 123", "", 123, 5),
    ("10 dobras", "", 42, 10),
    ("sem usuarios com >20 conversas", " AND u.convs_total <= 20", 42, 5),
    ("so 1a experiencia curta (<=1 conversa na 1a sessao)", " AND u.convs_1a_sessao = 1", 42, 5),
]

resultados = {}
with psycopg.connect(URL) as dw:
    for rotulo, extra, semente, k in VARIANTES:
        E.SQL, E.SEMENTE, E.K_DOBRAS = SQL0 + extra, semente, k
        for l in E.calcular(dw):
            chave = l[1] if not l[1].startswith("Tema") else l[2].split(" em vez")[0]
            if chave in FOCO:
                resultados.setdefault(chave, {})[rotulo] = (l[4], l[11], l[12], l[13])  # n, efeito, lo, hi

print(f"{'fator':<30}{'variante':<52}{'n':>6}{'ajustado pp [IC95]':>28}")
for chave in FOCO:
    for rotulo, _, _, _ in VARIANTES:
        if rotulo in resultados.get(chave, {}):
            n, ef, lo, hi = resultados[chave][rotulo]
            print(f"{chave:<30}{rotulo:<52}{n:>6}{ef:>10.2f} [{lo:>6.2f}; {hi:>6.2f}]")
    print()
