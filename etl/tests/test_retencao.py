"""RETENCAO POR ANOMALIA: o detector achou algo estranho (taxa de pais ou pico de semana novo), entao a carga fica RETIDA:
nada e publicado e os numeros do cliente continuam os da carga anterior, ate alguem aprovar de forma explicita.
  - anomalia sem aprovacao retem; com --aprovar-anomalias (ou ETL_APROVAR_ANOMALIAS=1) publica e registra o que foi aprovado
  - deriva e integridade continuam so alertando (nao retem)
  - uma carga retida nao se repete a cada `docker compose up` (a mesma semente espera a decisao); semente nova ou aprovacao refazem
"""
import pytest

import main
from camadas import bronze
from camadas.bronze.carregar import DESTINOS
from comum.qualidade import Resultado


def _exec(dw, status):
    return dw.execute("INSERT INTO ops.etl_execucao (versao_codigo, status) VALUES ('teste', %s) RETURNING id", (status,)).fetchone()[0]


def _res(transicao, passou=False):
    return Resultado(transicao, f"verificacao de {transicao}", "0", "1" if not passou else "0", passou)


@pytest.fixture(autouse=True)
def sem_aprovacao(monkeypatch):
    monkeypatch.delenv("ETL_APROVAR_ANOMALIAS", raising=False)
    monkeypatch.setattr(main.sys, "argv", ["main.py"])


def test_anomalia_sem_aprovacao_retem_a_carga(dw):
    e = _exec(dw, "rodando")
    alertas: list = []
    with pytest.raises(main.CargaRetida) as erro:
        main.conferir(dw, e, "anomalia", [_res("anomalia")], alertas)
    assert len(erro.value.anomalias) == 1


def test_anomalia_semanal_tambem_retem(dw):
    e = _exec(dw, "rodando")
    with pytest.raises(main.CargaRetida):
        main.conferir(dw, e, "anomalia_semanal", [_res("anomalia_semanal")], [])


def test_anomalia_aprovada_publica_e_fica_nos_alertas(dw, monkeypatch):
    monkeypatch.setattr(main.sys, "argv", ["main.py", "--aprovar-anomalias"])
    e = _exec(dw, "rodando")
    alertas: list = []
    main.conferir(dw, e, "anomalia", [_res("anomalia")], alertas)      # nao levanta
    assert [r.transicao for r in alertas] == ["anomalia"]


def test_aprovacao_por_variavel_de_ambiente(dw, monkeypatch):
    monkeypatch.setenv("ETL_APROVAR_ANOMALIAS", "1")
    assert main.anomalias_aprovadas()
    main.conferir(dw, _exec(dw, "rodando"), "anomalia", [_res("anomalia")], [])


def test_deriva_e_integridade_continuam_so_alertando(dw):
    e = _exec(dw, "rodando")
    alertas: list = []
    main.conferir(dw, e, "silver", [_res("deriva"), _res("integridade")], alertas)      # nao levanta
    assert len(alertas) == 2


def test_falha_de_conservacao_continua_derrubando_a_carga(dw):
    with pytest.raises(main.PortaoFalhou):
        main.conferir(dw, _exec(dw, "rodando"), "silver", [_res("bronze_silver")], [])


def test_conferencia_ok_nao_retem(dw):
    main.conferir(dw, _exec(dw, "rodando"), "anomalia", [_res("anomalia", passou=True)], [])


# ---- a carga retida espera a decisao: nao se repete a cada up ----
def _semente(tmp_path, conteudo=b"a"):
    for i, nome in enumerate(DESTINOS):
        (tmp_path / nome).write_bytes(conteudo + bytes([i]))
    return tmp_path


def _lotes(dw, exec_id, semente):
    for nome, sha in bronze.impressao_da_semente(semente).items():
        dw.execute("INSERT INTO ops.bronze_lote (execucao_id, arquivo, sha256, linhas, tamanho_bytes, tabela_destino) VALUES (%s, %s, %s, 1, 1, 'x')",
                   (exec_id, nome, sha))


def test_carga_retida_nao_se_repete_com_a_mesma_semente(dw, tmp_path):
    semente = _semente(tmp_path)
    publicada = _exec(dw, "ok")
    _lotes(dw, publicada, _semente(tmp_path, b"antiga"))                 # a publicada leu uma semente anterior
    retida = _exec(dw, "retida")
    _lotes(dw, retida, semente)                                          # a retida leu a semente atual
    precisa, motivo = main.carga_necessaria(dw, semente)
    assert not precisa and "retida" in motivo and str(retida) in motivo


def test_aprovar_ou_recarregar_refaz_mesmo_com_carga_retida(dw, tmp_path):
    semente = _semente(tmp_path)
    _lotes(dw, _exec(dw, "ok"), _semente(tmp_path, b"antiga"))
    _lotes(dw, _exec(dw, "retida"), semente)
    assert main.carga_necessaria(dw, semente, forcar=True)[0] is True


def test_semente_nova_depois_de_retida_recarrega(dw, tmp_path):
    antiga = _semente(tmp_path, b"antiga")
    _lotes(dw, _exec(dw, "ok"), antiga)
    _lotes(dw, _exec(dw, "retida"), antiga)
    nova = _semente(tmp_path, b"nova")                                   # outra semente: vale uma nova tentativa
    assert main.carga_necessaria(dw, nova)[0] is True


def test_retida_antiga_depois_de_uma_publicacao_nao_conta(dw, tmp_path):
    semente = _semente(tmp_path)
    _lotes(dw, _exec(dw, "retida"), semente)
    publicada = _exec(dw, "alerta")                                      # depois alguem aprovou: a retida ficou para tras
    _lotes(dw, publicada, semente)
    precisa, motivo = main.carga_necessaria(dw, semente)
    assert not precisa and "retida" not in motivo and "ja esta carregado" in motivo
