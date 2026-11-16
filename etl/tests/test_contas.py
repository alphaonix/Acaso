"""Contas de acesso: vem da migracao 029, so com o hash da senha (scrypt, sal proprio); nenhuma senha em texto."""


def test_migracao_traz_as_contas_de_quem_avalia_so_com_hash(dw):
    contas = {r[0]: r[1] for r in dw.execute("SELECT email, senha_hash FROM ops.usuario_dashboard")}
    assert set(contas) == {"nathalia.anjos@aca.so", "daniele.cardoso@aca.so"}
    assert all(h.startswith("scrypt$") and len(h.split("$")) == 6 for h in contas.values())
    assert len(set(contas.values())) == 2                       # sal proprio: hashes diferentes mesmo com a mesma senha


def test_fotos_so_aceitam_https(dw):
    fotos = [r[0] for r in dw.execute("SELECT foto_url FROM ops.usuario_dashboard")]
    assert all(f is None or f.startswith("https://") for f in fotos)