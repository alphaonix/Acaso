"""TESTE DOURADO do incidente (PDF, secao 4.2): reproduz, com dados sinteticos, a falha que fazia o retorno "cair" de 31% para 18%.
Causa: o usuario_id usava o user-agent BRUTO (uma atualizacao de navegador criava "outro usuario" e inflava os novos) e a
"primeira vez" era o ULTIMO turno em UTC. Aqui garantimos que a nossa definicao nao cai nessas armadilhas."""
from datetime import timedelta

from .helpers import C, UA_ANDROID, UA_CHROME_119, UA_CHROME_120, UA_FIREFOX, linhas, rodar, t, uid, usuario


def test_atualizar_o_navegador_nao_cria_outro_usuario(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("ip-1", ini, ua=UA_CHROME_119), C("ip-1", ini + timedelta(days=3), ua=UA_CHROME_120)])
    ids = linhas(dw, "SELECT usuario_id, convs_total FROM silver.fato_usuario WHERE usuario_id = %s", (uid("ip-1"),))
    assert ids == [(uid("ip-1"), 2)]       # um usuario com 2 conversas (a definicao do incidente daria 2 usuarios de 1 conversa)


def test_mudar_de_familia_de_navegador_ou_sistema_cria_outro_usuario(dw):
    # limite CONHECIDO da definicao (BDR-001): outro navegador, ou o celular, no mesmo IP, e outra "pessoa"
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("ip-1", ini, ua=UA_CHROME_119), C("ip-1", ini, ua=UA_FIREFOX), C("ip-1", ini, ua=UA_ANDROID)])
    n = linhas(dw, "SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil' AND usuario_id IN (%s, %s, %s)",
               (uid("ip-1", "Chrome/Windows"), uid("ip-1", "Firefox/Windows"), uid("ip-1", "Chrome/Android")))[0][0]
    assert n == 3


def test_reproduz_o_incidente_semanal_na_gold(dw):
    """5 usuarios chegam na semana de 13/11 (Chrome 119) e voltam 3 dias depois com o Chrome ja atualizado (120).
    Correto: 5 novos na semana de 13/11, 5 voltaram, e NENHUM novo "fantasma" na semana seguinte."""
    chegada = t("2023-11-14 12:00")
    convs = []
    for i in range(5):
        convs += [C(f"u{i}", chegada, ua=UA_CHROME_119), C(f"u{i}", chegada + timedelta(days=3), ua=UA_CHROME_120)]
    rodar(dw, convs, com_gold=True)
    semanas = linhas(dw, "SELECT semana::text, novos, elegiveis, voltaram_7d FROM gold.agg_retorno_semana "
                         "WHERE pais = 'Brazil' AND semana BETWEEN '2023-11-06' AND '2023-11-27' ORDER BY semana")
    assert semanas == [("2023-11-13", 5, 5, 5)]


def test_primeira_vez_e_o_inicio_da_conversa_e_nao_o_ultimo_turno(dw):
    # comeca no domingo 04/06 23:30 UTC (20:30 em Sao Paulo, semana de 29/05) e termina na segunda 05/06 00:30 UTC (21:30, semana de 05/06)
    rodar(dw, [C("u", t("2023-06-04 23:30"), fim=t("2023-06-05 00:30"))])
    u = usuario(dw, "u")
    assert u["primeira_vez_utc"] == t("2023-06-04 23:30")
    assert str(u["semana"]) == "2023-05-29"        # usando o ultimo turno em UTC cairia na semana de 05/06 (o erro do incidente)


def test_uma_conversa_longa_nao_e_um_retorno(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("u", ini, fim=ini + timedelta(hours=3))])        # dura 3 h, mas e UMA conversa
    u = usuario(dw, "u")
    assert u["convs_total"] == 1 and u["voltou_7d"] is False