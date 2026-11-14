"""Contas de acesso ao painel. NENHUMA conta nem senha real fica no repositorio: tudo vem do ambiente (.env)."""
import os
import secrets

import psycopg

from .seguranca import hash_senha


def garantir_conta_avaliacao(ops: psycopg.Connection) -> None:
    """Sincroniza as contas de acesso com o ambiente. NENHUMA conta nem senha real fica no repositorio.
      DASH_USERS     'email|Nome|url-da-foto;email|Nome' (a foto e opcional; padrao: uma conta generica de avaliacao)
      DASH_PASSWORD  se definida (em .env), vale para todas as contas e e a fonte de verdade;
                     se vazia, cada conta NOVA recebe uma senha aleatoria, mostrada UMA vez no log do ETL
                     (docker compose logs etl); conta que ja existe mantem a senha.
    Contas que nao estao na lista sao removidas (nenhuma senha antiga sobra no banco)."""
    padrao = "avaliacao@exemplo.com|Avaliação"
    senha_env = os.environ.get("DASH_PASSWORD") or None
    contas = []
    for item in (os.environ.get("DASH_USERS") or padrao).split(";"):
        email, _, resto = item.partition("|")
        nome, _, foto = resto.partition("|")
        email = email.strip().lower()
        foto = foto.strip()
        if email:
            contas.append((email, nome.strip() or email.split("@")[0].replace(".", " ").title(), foto if foto.startswith("https://") else None))
    for email, nome, foto in contas:
        existe = ops.execute("SELECT 1 FROM ops.usuario_dashboard WHERE email = %s", (email,)).fetchone() is not None
        if senha_env:
            senha = senha_env
        elif existe:
            ops.execute("UPDATE ops.usuario_dashboard SET nome = %s, foto_url = %s WHERE email = %s", (nome, foto, email))
            continue
        else:
            senha = secrets.token_urlsafe(9)
            print(f"[acesso] SENHA GERADA para {email}: {senha}   (mostrada so agora; para definir a sua, use DASH_PASSWORD no .env)", flush=True)
        ops.execute("""INSERT INTO ops.usuario_dashboard (email, nome, senha_hash, foto_url) VALUES (%s, %s, %s, %s)
                       ON CONFLICT (email) DO UPDATE SET nome = EXCLUDED.nome, senha_hash = EXCLUDED.senha_hash, foto_url = EXCLUDED.foto_url""",
                    (email, nome, hash_senha(senha), foto))
    ops.execute("DELETE FROM ops.usuario_dashboard WHERE NOT (email = ANY(%s))", ([c[0] for c in contas],))
    print(f"[acesso] contas ativas: {', '.join(c[0] for c in contas)}", flush=True)
