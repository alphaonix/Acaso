"""SIMULACAO DE CENARIOS: planta um defeito em uma camada, roda a carga de verdade, confere se o detector de anomalia aponta a camada certa e gera um
RELATORIO EM PDF (exports/relatorio_anomalias.pdf) com o funil, o resultado e a explicacao de por que pode ser anomalia ou alarme falso.

Roda num banco DESCARTAVEL (`retencao_cenarios`, no mesmo servidor): o banco real e a semente oficial nunca sao tocados. Uma carga normal e feita
uma vez (a referencia); cada cenario roda em seguida e e desfeito (rollback), entao um cenario nao contamina o seguinte.

Voce escolhe o que simular:
  docker compose --profile operacao run --rm simular-cenarios --listar                         lista os cenarios
  docker compose --profile operacao run --rm simular-cenarios bronze_sem_endereco gold_numerador     so esses
  docker compose --profile operacao run --rm simular-cenarios todos                           todos (cerca de 20 minutos)
"""
import os
import subprocess
import sys

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from simulacao import gerar_semente, relatorio_pdf
from simulacao.catalogo import CAMADA_TITULO, CATALOGO

BANCO = "retencao_cenarios"
SEMENTE_OFICIAL, CENARIOS = "/data/seed", "/data/cenarios"
SAIDA = os.environ.get("SAIDA", "/saida/relatorio_anomalias.pdf")


def url(dbname: str) -> str:
    return make_conninfo(**{**conninfo_to_dict(os.environ["DATABASE_URL"]), "dbname": dbname})


def semente_de(nome: str) -> str:
    s = CATALOGO[nome].semente
    return SEMENTE_OFICIAL if s == "oficial" else f"{CENARIOS}/{s}"


def carga(cenario: str, semente: str, estrito: bool) -> None:
    env = {**os.environ, "DATABASE_URL": url(BANCO), "SEED_DIR": semente, "QA_ESTRITO": "1" if estrito else "0", "CODE_VERSION": f"simulacao-{cenario}"}
    r = subprocess.run([sys.executable, "-m", "simulacao.executar", cenario], env=env, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        print(r.stdout[-1500:], r.stderr[-1500:])
        raise SystemExit(f"a carga do cenario '{cenario}' quebrou (exit {r.returncode})")
    if cenario != "base":                                         # o que o ETL disse sobre este cenario (o resumo completo vai para o PDF)
        for linha in r.stdout.splitlines():
            if linha.startswith("[anomalia-semanal]"):
                print("   " + linha[:260], flush=True)


def listar() -> None:
    print("Cenarios disponiveis (rode com o nome, varios nomes, ou 'todos'):\n")
    for camada in ("bronze", "silver", "gold", "codigo", "nenhuma"):
        print(f"  [{CAMADA_TITULO[camada]}]")
        for c in (c for c in CATALOGO.values() if c.camada == camada):
            print(f"    {c.nome:<26} {c.titulo}")
    print("\nExemplo: docker compose --profile operacao run --rm simular-cenarios bronze_sem_endereco silver_retorno_inflado gold_numerador")


def coletar(db, nome: str, exec_id: int) -> dict:
    c = CATALOGO[nome]
    linha = db.execute("""SELECT tipo, origem, taxa_referencia, taxa_atual, elegiveis_referencia, elegiveis_atual, z, resumo, sinais
                          FROM auditoria.anomalia WHERE execucao_id = %s AND pais = 'Brazil'""", (exec_id,)).fetchone()
    achado = None if linha is None else {"tipo": linha[0], "origem": linha[1], "taxa_ref": float(linha[2]), "taxa_atual": float(linha[3]), "eleg_ref": linha[4],
                                         "eleg_atual": linha[5], "z": None if linha[6] is None else float(linha[6]), "resumo": linha[7], "sinais": linha[8]}
    falhas = db.execute("""SELECT verificacao, esperado, obtido FROM ops.qa_resultado WHERE execucao_id = %s AND NOT passou
                           AND transicao NOT IN ('anomalia', 'deriva', 'integridade') ORDER BY id""", (exec_id,)).fetchall()
    apontada = achado["origem"] if achado else "sem alerta"
    # alertas semanais NOVOS em qualquer pais (o Brasil primeiro): um defeito de codigo, como o do incidente, afeta todos os paises, e os grandes mostram o sinal melhor
    semanais = [{"semana": s[0], "diagnostico": s[1], "camada": s[2], "novos": s[3], "novos_base": float(s[4]), "voltaram": s[5], "voltaram_base": float(s[6]),
                 "pct_endereco": None if s[7] is None else float(s[7]), "pct_endereco_base": None if s[8] is None else float(s[8]), "resumo": s[9], "pais": s[10]}
                for s in db.execute("""SELECT semana::text, diagnostico, camada, novos, novos_base, voltaram, voltaram_base, pct_endereco, pct_endereco_base, resumo, pais
                                       FROM auditoria.anomalia_semanal WHERE execucao_id = %s AND nova
                                       ORDER BY (pais <> 'Brazil'), (diagnostico <> 'PESSOA_DIVIDIDA'), pais, semana""", (exec_id,)).fetchall()]
    diagnosticos = {s["diagnostico"] for s in semanais}
    ok_carga = c.esperada == "QUALQUER" or apontada == (c.esperada or "sem alerta")
    ok_semanal = True if not c.avaliar_semanal else ((c.esperada_semanal in diagnosticos) if c.esperada_semanal else not diagnosticos)
    return {"cenario": c, "achado": achado, "apontada": apontada, "ok": ok_carga and ok_semanal, "gate_falhas": falhas, "gate_n": len(falhas),
            "semanais": semanais, "ok_semanal": ok_semanal}


def main(argv: list[str]) -> int:
    if not argv or "--listar" in argv:
        listar()
        return 0
    escolhidos = list(CATALOGO) if "todos" in argv else argv
    desconhecidos = [n for n in escolhidos if n not in CATALOGO]
    if desconhecidos:
        print(f"Cenario desconhecido: {', '.join(desconhecidos)}\n")
        listar()
        return 2
    assert conninfo_to_dict(os.environ["DATABASE_URL"])["dbname"] != BANCO
    adm = psycopg.connect(url("postgres"), autocommit=True)
    adm.execute(f"DROP DATABASE IF EXISTS {BANCO} WITH (FORCE)")
    adm.execute(f"CREATE DATABASE {BANCO}")
    gerar_semente.gerar()
    print("\n== Carga normal (a referencia de todos os cenarios) ==", flush=True)
    carga("base", SEMENTE_OFICIAL, True)
    resultados = []
    for nome in escolhidos:
        print(f"== Cenario '{nome}' ==", flush=True)
        carga(nome, semente_de(nome), False)
        with psycopg.connect(url(BANCO), autocommit=True) as db:
            exec_id = db.execute("SELECT max(id) FROM ops.etl_execucao").fetchone()[0]
            r = coletar(db, nome, exec_id)
        resultados.append(r)
        a = r["achado"]
        c = CATALOGO[nome]
        print(f"   esperada: {c.esperada or 'sem alerta'} | apontada: {r['apontada']}"
              + (f" | taxa {a['taxa_ref'] * 100:.1f}% -> {a['taxa_atual'] * 100:.1f}% ({a['tipo']})" if a else "")
              + (f" | semanal esperado: {c.esperada_semanal or 'nenhum'}, apontado: {', '.join(sorted({s['diagnostico'] for s in r['semanais']})) or 'nenhum'}" if c.avaliar_semanal else "")
              + f" | {'OK' if r['ok'] else 'ERRADO'}", flush=True)
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    relatorio_pdf.gerar(resultados, SAIDA)
    adm.execute(f"DROP DATABASE IF EXISTS {BANCO} WITH (FORCE)")
    print(f"\nRelatorio em PDF: {SAIDA} (no seu computador: exports/relatorio_anomalias.pdf)")
    print("RESULTADO:", "todos os cenarios conferem" if all(r["ok"] for r in resultados) else "HA CENARIOS QUE NAO CONFEREM")
    return 0 if all(r["ok"] for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
