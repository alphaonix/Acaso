"""TESTE PONTA A PONTA DO DETECTOR DE ANOMALIA: planta um defeito em cada camada, roda a carga de verdade e confere se a origem apontada e a certa.

Roda num banco DESCARTAVEL (`retencao_cenarios`, no mesmo servidor): o banco real e a semente oficial nunca sao tocados.
Para cada cenario: (1) carga normal com a semente oficial (a referencia); (2) carga com o defeito, sem derrubar a carga (QA_ESTRITO=0), para
ver tambem o que o portao de qualidade diz; (3) le auditoria.anomalia e compara a origem apontada com a esperada.

  cenario         defeito plantado                                                              origem esperada
  bronze          semente nova: 60% das conversas do Brasil sem endereco (a fonte falhou)       BRONZE
  silver          semente nova e saudavel + regra de elegibilidade da silver errada             SILVER
  gold            semente nova e saudavel + agregacao da gold errada (triplica os que voltaram) GOLD
  transformacao   MESMA semente oficial + regra de elegibilidade errada                         TRANSFORMACAO

Uso:  docker compose --profile operacao run --rm simular-cenarios        (cerca de 15 minutos; sai com erro se alguma origem estiver errada)
"""
import os
import subprocess
import sys

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from simulacao import gerar_semente

BANCO = "retencao_cenarios"
SEMENTE_OFICIAL, CENARIOS = "/data/seed", "/data/cenarios"
# cenario -> (semente, origem esperada)
PLANO = {"bronze": (f"{CENARIOS}/bronze", "BRONZE"), "silver": (f"{CENARIOS}/nova", "SILVER"),
         "gold": (f"{CENARIOS}/nova", "GOLD"), "transformacao": (SEMENTE_OFICIAL, "TRANSFORMACAO")}


def url(dbname: str) -> str:
    return make_conninfo(**{**conninfo_to_dict(os.environ["DATABASE_URL"]), "dbname": dbname})


def carga(cenario: str, semente: str, estrito: bool) -> int:
    env = {**os.environ, "DATABASE_URL": url(BANCO), "SEED_DIR": semente, "QA_ESTRITO": "1" if estrito else "0", "CODE_VERSION": f"simulacao-{cenario}"}
    r = subprocess.run([sys.executable, "-m", "simulacao.executar", cenario], env=env, capture_output=True, text=True)
    linhas = [l for l in r.stdout.splitlines() if l.startswith(("[anomalia]", "ETL", "[qa] FALHOU", "[integridade] ALTERADO"))]
    print("\n".join(f"    {l}" for l in linhas[:60]), flush=True)
    if r.returncode not in (0, 1):
        print(r.stderr[-1500:])
    return r.returncode


def main() -> int:
    assert os.environ["DATABASE_URL"] and conninfo_to_dict(os.environ["DATABASE_URL"])["dbname"] != BANCO
    adm = psycopg.connect(url("postgres"), autocommit=True)
    adm.execute(f"DROP DATABASE IF EXISTS {BANCO} WITH (FORCE)")
    adm.execute(f"CREATE DATABASE {BANCO}")
    gerar_semente.gerar()
    resultado = []
    escolhidos = [a for a in sys.argv[1:] if a in PLANO] or list(PLANO)       # opcional: rodar so alguns cenarios (ex.: ... bronze gold)
    for nome, (semente, esperada) in ((n, PLANO[n]) for n in escolhidos):
        print(f"\n=== Cenario '{nome}' (origem esperada: {esperada}) ===\n  1) carga normal (referencia)", flush=True)
        carga("base", SEMENTE_OFICIAL, True)
        print(f"  2) carga com o defeito '{nome}'", flush=True)
        carga(nome, semente, False)
        with psycopg.connect(url(BANCO), autocommit=True) as db:
            exec_id = db.execute("SELECT max(id) FROM ops.etl_execucao").fetchone()[0]
            achadas = db.execute("SELECT pais, round(taxa_referencia * 100, 1), round(taxa_atual * 100, 1), origem FROM auditoria.anomalia WHERE execucao_id = %s", (exec_id,)).fetchall()
            gate = db.execute("SELECT count(*) FROM ops.qa_resultado WHERE execucao_id = %s AND NOT passou AND transicao NOT IN ('anomalia', 'deriva', 'integridade')", (exec_id,)).fetchone()[0]
        br = [a for a in achadas if a[0] == "Brazil"]
        ok = len(br) == 1 and br[0][3] == esperada
        resultado.append((nome, esperada, br[0][3] if br else "NENHUMA", gate, ok))
        print(f"  => anomalia: {br[0][1]}% -> {br[0][2]}%, origem apontada: {br[0][3]}" if br else "  => NENHUMA anomalia apontada para o Brasil", flush=True)
    print("\n=== RESUMO ===\n cenario        esperada       apontada       conferencias do portao que falharam   resultado")
    for nome, esperada, apontada, gate, ok in resultado:
        print(f" {nome:<14} {esperada:<14} {apontada:<14} {gate:<37} {'OK' if ok else 'ERRADO'}")
    adm.execute(f"DROP DATABASE IF EXISTS {BANCO} WITH (FORCE)")
    return 0 if all(r[4] for r in resultado) else 1


if __name__ == "__main__":
    sys.exit(main())
