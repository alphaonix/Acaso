"""O que a silver exclui, mantem e como trata vazios (BDR-001). Nada pode sumir sem registro: bronze = silver + excluidas."""
from datetime import timedelta

from .helpers import C, linhas, rodar, t


def _silver_do_brasil(dw, ip):
    return linhas(dw, "SELECT count(*) FROM silver.fato_conversa WHERE usuario_id IN (SELECT usuario_id FROM silver.fato_usuario) "
                      "AND conversation_hash LIKE %s", (f"{ip}%",))[0][0]


def test_copia_exata_e_excluida_e_fica_a_primeira(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("u", ini, hash="x1"), C("u", ini, hash="x1")])      # mesmo hash, IP e inicio
    assert linhas(dw, "SELECT count(*) FROM silver.fato_conversa WHERE conversation_hash = 'x1'")[0][0] == 1


def test_mesmo_hash_com_ip_ou_inicio_diferentes_sao_conversas_distintas(dw):
    ini = t("2023-06-01 10:00")
    rodar(dw, [C("a", ini, hash="x2"), C("b", ini, hash="x2"), C("a", ini + timedelta(days=1), hash="x2")])
    assert linhas(dw, "SELECT count(*) FROM silver.fato_conversa WHERE conversation_hash = 'x2'")[0][0] == 3


def test_sem_ip_ou_sem_inicio_e_excluida(dw):
    rodar(dw, [C(None, t("2023-06-01 10:00"), hash="sem-ip"), C("u", None, hash="sem-inicio"), C("u", t("2023-06-01 10:00"), hash="ok")])
    assert linhas(dw, "SELECT conversation_hash FROM silver.fato_conversa WHERE conversation_hash IN ('sem-ip','sem-inicio','ok') ORDER BY 1") == [("ok",)]


def test_pais_vazio_vira_desconhecido_e_a_linha_fica(dw):
    rodar(dw, [C("u", t("2023-06-01 10:00"), pais=None, hash="sem-pais")])
    assert linhas(dw, "SELECT pais FROM silver.fato_conversa WHERE conversation_hash = 'sem-pais'") == [("Desconhecido",)]


def test_conservacao_bronze_igual_silver_mais_excluidas(dw):
    ini = t("2023-06-01 10:00")
    convs = [C("u", ini, hash="d"), C("u", ini, hash="d"), C(None, ini, hash="n1"), C("v", None, hash="n2"), C("w", ini, hash="ok")]
    rodar(dw, convs)
    bronze = linhas(dw, "SELECT count(*) FROM bronze.wildchat")[0][0]
    silver = linhas(dw, "SELECT count(*) FROM silver.fato_conversa")[0][0]
    assert bronze - silver == 3          # 1 copia exata + 1 sem IP + 1 sem inicio (as 2 ancoras e as 2 conversas validas ficam)


def test_silver_aponta_para_a_linha_da_bronze(dw):
    rodar(dw, [C("u", t("2023-06-01 10:00"), hash="rastro")])
    r = linhas(dw, "SELECT b.conversation_hash FROM silver.fato_conversa f JOIN bronze.wildchat b USING (bronze_id) WHERE f.conversation_hash = 'rastro'")
    assert r == [("rastro",)]