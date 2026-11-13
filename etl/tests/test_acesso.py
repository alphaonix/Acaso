"""Contas de acesso: nenhuma conta nem senha real no repositorio; sem configuracao, uma conta generica com senha aleatoria."""
import main


def _hash(dw, email):
    r = dw.execute("SELECT senha_hash FROM ops.usuario_dashboard WHERE email = %s", (email,)).fetchone()
    return r[0] if r else None


def test_sem_configuracao_cria_conta_generica_com_senha_aleatoria(dw, monkeypatch, capsys):
    monkeypatch.delenv("DASH_USERS", raising=False)
    monkeypatch.delenv("DASH_PASSWORD", raising=False)
    main.garantir_conta_avaliacao(dw)
    saida = capsys.readouterr().out
    assert "SENHA GERADA para avaliacao@exemplo.com" in saida
    assert dw.execute("SELECT email FROM ops.usuario_dashboard").fetchall() == [("avaliacao@exemplo.com",)]
    assert saida.count("SENHA GERADA") == 1             # a senha aparece uma unica vez


def test_segunda_subida_mantem_a_senha_e_nao_a_mostra_de_novo(dw, monkeypatch, capsys):
    monkeypatch.delenv("DASH_USERS", raising=False)
    monkeypatch.delenv("DASH_PASSWORD", raising=False)
    main.garantir_conta_avaliacao(dw)
    antes = _hash(dw, "avaliacao@exemplo.com")
    capsys.readouterr()
    main.garantir_conta_avaliacao(dw)
    assert _hash(dw, "avaliacao@exemplo.com") == antes
    assert "SENHA GERADA" not in capsys.readouterr().out


def test_com_env_a_senha_definida_vale_e_contas_fora_da_lista_saem(dw, monkeypatch, capsys):
    monkeypatch.setenv("DASH_USERS", "a@exemplo.com|Ana;b@exemplo.com|Beto")
    monkeypatch.setenv("DASH_PASSWORD", "senha-do-env")
    main.garantir_conta_avaliacao(dw)
    assert "SENHA GERADA" not in capsys.readouterr().out
    assert {r[0] for r in dw.execute("SELECT email FROM ops.usuario_dashboard")} == {"a@exemplo.com", "b@exemplo.com"}
    monkeypatch.setenv("DASH_USERS", "a@exemplo.com|Ana")
    main.garantir_conta_avaliacao(dw)
    assert {r[0] for r in dw.execute("SELECT email FROM ops.usuario_dashboard")} == {"a@exemplo.com"}

def test_foto_e_opcional_e_so_aceita_https(dw, monkeypatch):
    monkeypatch.setenv("DASH_USERS", "a@exemplo.com|Ana|https://exemplo.com/a.jpg;b@exemplo.com|Beto;c@exemplo.com|Cris|http://inseguro/c.jpg")
    monkeypatch.setenv("DASH_PASSWORD", "senha-do-env")
    main.garantir_conta_avaliacao(dw)
    fotos = dict(dw.execute("SELECT email, foto_url FROM ops.usuario_dashboard").fetchall())
    assert fotos == {"a@exemplo.com": "https://exemplo.com/a.jpg", "b@exemplo.com": None, "c@exemplo.com": None}
