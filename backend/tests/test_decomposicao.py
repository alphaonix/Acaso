"""Decomposicao shift-share (mix x taxa x interacao): as tres partes somam EXATAMENTE a variacao do retorno."""
import random

import pytest

from app.decomposicao import decompor


def test_so_o_mix_mudou():
    # as taxas por perfil sao iguais nos dois meses; so a composicao muda: tudo e mix
    por_mes = {"a": {"x": (80, 40), "y": (20, 2)}, "b": {"x": (20, 10), "y": (80, 8)}}
    r = decompor(por_mes, "a", "b")
    assert r["componentes_pp"]["taxa"] == pytest.approx(0) and r["componentes_pp"]["interacao"] == pytest.approx(0)
    assert r["componentes_pp"]["mix"] == pytest.approx(r["delta_pp"]) and r["soma_confere"]


def test_so_a_taxa_mudou():
    # a composicao e a mesma; so o retorno dentro de cada perfil muda
    por_mes = {"a": {"x": (50, 25), "y": (50, 10)}, "b": {"x": (50, 15), "y": (50, 5)}}
    r = decompor(por_mes, "a", "b")
    assert r["componentes_pp"]["mix"] == pytest.approx(0) and r["componentes_pp"]["interacao"] == pytest.approx(0)
    assert r["componentes_pp"]["taxa"] == pytest.approx(r["delta_pp"]) and r["delta_pp"] == pytest.approx(-15)


def test_nada_mudou():
    por_mes = {"a": {"x": (10, 5)}, "b": {"x": (10, 5)}}
    assert decompor(por_mes, "a", "b")["delta_pp"] == pytest.approx(0)


def test_nivel_que_aparece_so_em_um_mes():
    por_mes = {"a": {"x": (100, 30)}, "b": {"x": (50, 10), "novo": (50, 25)}}
    r = decompor(por_mes, "a", "b")
    assert r["soma_confere"] and r["delta_pp"] == pytest.approx((35 / 100 - 30 / 100) * 100)


@pytest.mark.parametrize("semente", range(25))
def test_propriedade_a_soma_sempre_confere(semente):
    """Para qualquer combinacao de perfis e contagens, mix + taxa + interacao = variacao (tolerancia numerica 1e-9)."""
    rnd = random.Random(semente)
    niveis = [f"n{i}" for i in range(rnd.randint(1, 8))]
    def mes():
        d = {}
        for k in niveis:
            if rnd.random() < 0.85:
                n = rnd.randint(1, 500)
                d[k] = (n, rnd.randint(0, n))
        return d or {niveis[0]: (10, 3)}
    por_mes = {"a": mes(), "b": mes()}
    r = decompor(por_mes, "a", "b")
    c = r["componentes_pp"]
    assert r["soma_confere"]
    assert c["mix"] + c["taxa"] + c["interacao"] == pytest.approx(r["delta_pp"], abs=1e-7)