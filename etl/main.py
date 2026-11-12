"""ETL em camadas: bronze -> silver -> gold, tudo no Postgres, com portao de qualidade (ADR-004).

  1. migrar      aplica db/migrations/*.sql em ordem
  2. registrar   registra cada arquivo da semente (sha256, linhas, tabela de destino) em ops.bronze_lote  [linhagem]
  3. bronze      carrega o dado bruto, sem alterar, na tabela bronze.wildchat (DuckDB le o Parquet; COPY grava no Postgres)
  4. silver      SQL no Postgres LENDO a bronze: limpeza, usuario, sessao, variaveis da 1a experiencia (BDR-001/003)
  5. gold        agregados, lista de paises e catalogo de indicadores (SQL no Postgres, lendo a silver)
  6. estimar     efeitos ajustados com IC (gold.efeito_fator)
  7. auditoria   linhagem entre camadas (schema auditoria): contagens, linhas excluidas, nulos, antes/depois, funil por pais
  8. qualidade   confere por transicao entre camadas e contra os numeros validados; se falhar (QA_ESTRITO=1), ROLLBACK e erro
Bronze, silver e gold sao reconstruidas por inteiro em UMA transacao: a API nunca ve um estado pela metade.
"""
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

import duckdb
import psycopg

from pipeline import auditoria, bronze, estimar, gold, qa, silver
from pipeline.seguranca import hash_senha

DATABASE_URL = os.environ["DATABASE_URL"]
MIGRACOES = Path(os.environ.get("MIGRATIONS_DIR", "/migrations"))
SEMENTE = Path(os.environ.get("SEED_DIR", "/data/seed"))
ESTRITO = os.environ.get("QA_ESTRITO", "1") == "1"
VERSAO = os.environ.get("CODE_VERSION", "dev")


def conectar(autocommit: bool, tentativas: int = 30) -> psycopg.Connection:
    for _ in range(tentativas):
        try:
            return psycopg.connect(DATABASE_URL, autocommit=autocommit)
        except psycopg.OperationalError:
            time.sleep(1)
    sys.exit("ETL: banco indisponivel")


def migrar(ops: psycopg.Connection) -> None:
    ops.execute("CREATE TABLE IF NOT EXISTS public.schema_migrations (arquivo text PRIMARY KEY, aplicada_em timestamptz DEFAULT now())")
    feitas = {r[0] for r in ops.execute("SELECT arquivo FROM public.schema_migrations")}
    for sql in sorted(MIGRACOES.glob("*.sql")):
        if sql.name not in feitas:
            print(f"[migrar] {sql.name}", flush=True)
            ops.execute(sql.read_text(encoding="utf-8"))
            ops.execute("INSERT INTO public.schema_migrations (arquivo) VALUES (%s)", (sql.name,))


def garantir_conta_avaliacao(ops: psycopg.Connection) -> None:
    """Sincroniza as contas de acesso com o ambiente. NENHUMA conta nem senha real fica no repositorio.
      DASH_USERS     'email|Nome;email|Nome' (padrao: uma conta generica de avaliacao)
      DASH_PASSWORD  se definida (em .env), vale para todas as contas e e a fonte de verdade;
                     se vazia, cada conta NOVA recebe uma senha aleatoria, mostrada UMA vez no log do ETL
                     (docker compose logs etl); conta que ja existe mantem a senha.
    Contas que nao estao na lista sao removidas (nenhuma senha antiga sobra no banco)."""
    padrao = "avaliacao@exemplo.com|Avaliação"
    senha_env = os.environ.get("DASH_PASSWORD") or None
    contas = []
    for item in (os.environ.get("DASH_USERS") or padrao).split(";"):
        email, _, nome = item.partition("|")
        email = email.strip().lower()
        if email:
            contas.append((email, nome.strip() or email.split("@")[0].replace(".", " ").title()))
    for email, nome in contas:
        existe = ops.execute("SELECT 1 FROM ops.usuario_dashboard WHERE email = %s", (email,)).fetchone() is not None
        if senha_env:
            senha = senha_env
        elif existe:
            ops.execute("UPDATE ops.usuario_dashboard SET nome = %s WHERE email = %s", (nome, email))
            continue
        else:
            senha = secrets.token_urlsafe(9)
            print(f"[acesso] SENHA GERADA para {email}: {senha}   (mostrada so agora; para definir a sua, use DASH_PASSWORD no .env)", flush=True)
        ops.execute("""INSERT INTO ops.usuario_dashboard (email, nome, senha_hash) VALUES (%s, %s, %s)
                       ON CONFLICT (email) DO UPDATE SET nome = EXCLUDED.nome, senha_hash = EXCLUDED.senha_hash""",
                    (email, nome, hash_senha(senha)))
    ops.execute("DELETE FROM ops.usuario_dashboard WHERE NOT (email = ANY(%s))", ([e for e, _ in contas],))
    print(f"[acesso] contas ativas: {', '.join(e for e, _ in contas)}", flush=True)

def registrar_lotes(ops: psycopg.Connection, con: duckdb.DuckDBPyConnection, exec_id: int) -> None:
    for nome, tabela in bronze.DESTINOS.items():
        arq = SEMENTE / nome
        if not arq.exists():
            sys.exit(f"ETL: semente ausente: {arq} (rode python etl/make_seed.py)")
        sha = hashlib.sha256(arq.read_bytes()).hexdigest()
        linhas = con.execute(f"SELECT count(*) FROM read_parquet('{arq.as_posix()}')").fetchone()[0]
        ops.execute("""INSERT INTO ops.bronze_lote (execucao_id, arquivo, sha256, linhas, tamanho_bytes, tabela_destino)
                       VALUES (%s, %s, %s, %s, %s, %s)""", (exec_id, nome, sha, linhas, arq.stat().st_size, tabela))
        print(f"[bronze] {nome}: {linhas} linhas, sha256 {sha[:12]} -> {tabela}", flush=True)


def limpar(dw: psycopg.Connection) -> None:
    """Esvazia as tres camadas dentro da transacao (a API so ve o estado antigo ate o COMMIT)."""
    with dw.cursor() as cur:
        cur.execute("""TRUNCATE bronze.wildchat,
                       gold.pais, gold.agg_retorno_semana, gold.agg_retorno_fator, gold.agg_uso_dia, gold.agg_retorno_mes_fator, gold.problema_qualidade, gold.efeito_fator, gold.catalogo_indicador,
                       silver.fato_conversa, silver.fato_usuario, silver.dim_tema, silver.dim_pais RESTART IDENTITY""")


def finalizar(ops, exec_id, status, lidas=None, carregadas=None, obs=None) -> None:
    ops.execute("UPDATE ops.etl_execucao SET finalizado_em = now(), status = %s, linhas_lidas = %s, linhas_carregadas = %s, observacao = %s WHERE id = %s",
                (status, lidas, carregadas, obs, exec_id))


def main() -> int:
    ops = conectar(autocommit=True)
    migrar(ops)
    garantir_conta_avaliacao(ops)
    exec_id = ops.execute("INSERT INTO ops.etl_execucao (versao_codigo) VALUES (%s) RETURNING id", (VERSAO,)).fetchone()[0]
    dw = None
    try:
        con = duckdb.connect()
        registrar_lotes(ops, con, exec_id)
        dw = conectar(autocommit=False)
        limpar(dw)
        t0 = time.time()
        for arquivo, n in bronze.carregar(dw, con, SEMENTE).items():
            print(f"[bronze] {arquivo}: {n} linhas carregadas em {bronze.TABELA}", flush=True)
        t1 = time.time()
        dados = silver.construir(dw)
        print(f"[silver] lidas={dados['lidas']} carregadas={dados['carregadas']} sem_inicio={dados['sem_inicio']} "
              f"sem_ip={dados['sem_ip']} duplicadas={dados['duplicadas']} pais_nulo={dados['pais_nulo']} "
              f"(bronze {t1 - t0:.0f}s, silver {time.time() - t1:.0f}s)", flush=True)
        gold.construir(dw)
        print(f"[estimar] {estimar.estimar(dw)} efeitos gravados em gold.efeito_fator", flush=True)
        aud = auditoria.registrar(dw, exec_id)
        print(f"[auditoria] {aud['excluidas']} linhas excluidas registradas; {aud['exemplos_antes_depois']} exemplos antes/depois", flush=True)
        resultados = qa.verificar(dw, exec_id)
        qa.gravar(ops, exec_id, resultados)
        falhas = [r for r in resultados if not r.passou]
        for r in resultados:
            print(f"[qa] {'OK ' if r.passou else 'FALHOU'} [{r.transicao}] {r.verificacao}: esperado {r.esperado}, obtido {r.obtido}", flush=True)
        obs = json.dumps(dados)
        if falhas and ESTRITO:
            dw.rollback()
            finalizar(ops, exec_id, "falhou", dados["lidas"], 0, f"{len(falhas)} verificacao(oes) falharam; nada publicado. {obs}")
            print("ETL: portao de qualidade FALHOU; carga revertida.", flush=True)
            return 1
        dw.commit()
        finalizar(ops, exec_id, "alerta" if falhas else "ok", dados["lidas"], dados["carregadas"], obs)
        print(f"ETL concluido ({'com alertas' if falhas else 'ok'}).", flush=True)
        return 0
    except Exception as e:
        if dw is not None:
            dw.rollback()
        finalizar(ops, exec_id, "erro", obs=str(e)[:500])
        raise


if __name__ == "__main__":
    sys.exit(main())
