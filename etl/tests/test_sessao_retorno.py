"""Sessao, retorno em 7 dias, primeira experiencia e elegibilidade (BDR-001). Cada teste fixa UMA regra de borda:
se alguem mudar a definicao do indicador, o teste correspondente quebra e a mudanca deixa de passar despercebida."""
from datetime import timedelta

from pipeline.definicoes import GAP_SESSAO_MIN, JANELA_RETORNO_DIAS, LAVAGEM_DIAS

from .helpers import C, rodar, t, usuario


def test_parametros_da_definicao():
    # contrato: mudar um destes numeros muda TODO indicador do dashboard. Se mudar de proposito, atualize BDR-001 e este teste.
    assert (GAP_SESSAO_MIN, JANELA_RETORNO_DIAS, LAVAGEM_DIAS) == (30, 7, 30)


def test_ate_30_min_depois_do_fim_e_a_mesma_sessao(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("u", ini, fim=ini + timedelta(minutes=10)), C("u", ini + timedelta(minutes=40))])   # 30 min exatos depois do fim
    u = usuario(dw, "u")
    assert u["convs_total"] == 2 and u["convs_1a_sessao"] == 2
    assert u["voltou_7d"] is False                      # a propria sessao da 1a experiencia nao conta como retorno


def test_mais_de_30_min_abre_nova_sessao_e_conta_como_retorno(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("u", ini, fim=ini + timedelta(minutes=10)), C("u", ini + timedelta(minutes=40, seconds=1))])
    u = usuario(dw, "u")
    assert u["convs_1a_sessao"] == 1 and u["voltou_7d"] is True


def test_retorno_no_limite_de_7_dias(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("exato", ini), C("exato", ini + timedelta(days=7)),                                   # 7 dias exatos: conta
               C("passou", ini), C("passou", ini + timedelta(days=7, seconds=1))])                      # 1 s depois: nao conta
    assert usuario(dw, "exato")["voltou_7d"] is True
    assert usuario(dw, "passou")["voltou_7d"] is False


def test_qualquer_sessao_posterior_dentro_da_janela_conta(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("u", ini), C("u", ini + timedelta(days=3)), C("u", ini + timedelta(days=20))])
    assert usuario(dw, "u")["voltou_7d"] is True


def test_sem_segunda_conversa_nao_voltou(dw):
    rodar(dw, [C("u", t("2023-06-01 10:00"))])
    assert usuario(dw, "u")["voltou_7d"] is False


def test_primeira_experiencia_e_a_primeira_conversa(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("u", ini, modelo="gpt-3.5-turbo", turnos=1), C("u", ini + timedelta(days=2), modelo="gpt-4", turnos=9)])
    u = usuario(dw, "u")
    assert u["modelo"] == "gpt-3.5-turbo" and u["turnos"] == 1 and u["primeira_vez_utc"] == ini


def test_elegibilidade_exige_30_dias_do_inicio_e_7_dias_do_fim(dw):
    # periodo dos dados: 2023-01-01 10:00 a 2023-12-31 10:00 (ancoras)
    casos = {
        "cedo": t("2023-01-31 09:59"),        # 1 min antes de inicio + 30 dias: ainda "lavagem"
        "borda_ini": t("2023-01-31 10:00"),   # exatamente inicio + 30 dias: elegivel
        "meio": t("2023-06-15 10:00"),
        "borda_fim": t("2023-12-24 10:00"),   # exatamente fim - 7 dias: elegivel
        "tarde": t("2023-12-24 10:01"),       # a janela de 7 dias nao fecha antes do fim dos dados
    }
    rodar(dw, [C(ip, quando) for ip, quando in casos.items()])
    esperado = {"cedo": False, "borda_ini": True, "meio": True, "borda_fim": True, "tarde": False}
    assert {ip: usuario(dw, ip)["elegivel"] for ip in casos} == esperado


def test_semana_hora_e_dia_no_fuso_do_pais(dw):
    # 08/05/2023 01:30 UTC = domingo 07/05 22:30 em Sao Paulo (UTC-3): a semana comeca na segunda 01/05, nao em 08/05
    rodar(dw, [C("u", t("2023-05-08 01:30"))])
    u = usuario(dw, "u")
    assert str(u["semana"]) == "2023-05-01" and u["hora"] == 22 and u["dia_semana"] == 7