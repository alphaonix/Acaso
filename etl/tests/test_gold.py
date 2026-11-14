"""Gold: intervalo de confianca (Wilson), amostra minima e agregados conferidos contra a silver."""
import pytest

from comum.definicoes import AMOSTRA_MINIMA

from .helpers import C, linhas, rodar, t


@pytest.mark.parametrize("x, n, lo, hi", [(50, 100, 0.4038, 0.5962), (0, 100, 0.0, 0.0370), (10, 10, 0.7225, 1.0)])
def test_wilson(dw, x, n, lo, hi):
    obtido_lo, obtido_hi = linhas(dw, "SELECT gold.wilson_lo(%s, %s), gold.wilson_hi(%s, %s)", (x, n, x, n))[0]
    assert float(obtido_lo) == pytest.approx(lo, abs=1e-3) and float(obtido_hi) == pytest.approx(hi, abs=1e-3)


def test_amostra_minima_esconde_a_taxa(dw):
    # 3 usuarios elegiveis (< AMOSTRA_MINIMA): a taxa e o IC ficam NULOS e a tela mostra "amostra pequena demais"
    assert AMOSTRA_MINIMA == 30
    rodar(dw, [C(f"u{i}", t("2023-06-14 10:00")) for i in range(3)], com_gold=True)
    assert linhas(dw, "SELECT elegiveis, taxa, ic_lo FROM gold.agg_retorno_semana WHERE pais = 'Brazil' AND semana = '2023-06-12'") == [(3, None, None)]


def test_taxa_de_retorno_da_semana(dw):
    # 40 usuarios na mesma semana; 10 voltam em ate 7 dias: 10/40 = 25%
    convs = []
    for i in range(40):
        convs.append(C(f"u{i}", t("2023-06-14 10:00")))
        if i < 10:
            convs.append(C(f"u{i}", t("2023-06-16 10:00")))
    rodar(dw, convs, com_gold=True)
    novos, el, vol, taxa = linhas(dw, "SELECT novos, elegiveis, voltaram_7d, taxa FROM gold.agg_retorno_semana WHERE pais = 'Brazil' AND semana = '2023-06-12'")[0]
    assert (novos, el, vol) == (40, 40, 10) and float(taxa) == pytest.approx(0.25)


def test_gold_soma_o_que_a_silver_tem(dw):
    rodar(dw, [C(f"u{i}", t("2023-06-14 10:00")) for i in range(7)], com_gold=True)
    silver = linhas(dw, "SELECT count(*) FILTER (WHERE elegivel) FROM silver.fato_usuario")[0][0]
    gold = linhas(dw, "SELECT sum(elegiveis) FROM gold.agg_retorno_semana")[0][0]
    assert gold == silver