"""SIMULACAO: o catalogo de cenarios esta completo e o relatorio em PDF e gerado (sem precisar rodar cargas)."""
import pytest

from comum import anomalia
from simulacao import relatorio_pdf
from simulacao.catalogo import CAMADA_TITULO, CATALOGO
from simulacao.executar import DEFEITOS

from .test_anomalia import REF, medidas

ORIGENS = {"BRONZE", "SILVER", "GOLD", "TRANSFORMACAO", None}


def test_ha_cenarios_que_comecam_em_cada_camada():
    for camada in ("bronze", "silver", "gold"):
        assert len([c for c in CATALOGO.values() if c.camada == camada]) >= 3, camada


@pytest.mark.parametrize("nome", list(CATALOGO))
def test_cada_cenario_tem_explicacao_completa(nome):
    c = CATALOGO[nome]
    assert c.nome == nome and c.camada in CAMADA_TITULO and c.esperada in ORIGENS
    assert len(c.titulo) > 10
    for campo in (c.defeito, c.anomalia_real, c.alarme_falso):
        assert len(campo) > 40, f"{nome}: texto curto demais"
    assert c.verificar, f"{nome}: sem passos de verificacao"


def test_cada_defeito_de_codigo_do_catalogo_existe_no_executor():
    for c in CATALOGO.values():
        if c.camada in ("silver", "gold", "codigo"):
            assert c.nome in DEFEITOS, c.nome


def _resultado(nome):
    c = CATALOGO[nome]
    a = anomalia.detectar(medidas(nulos_ip=6000, ips=1500, conv=4000, pessoas=1200, eleg=800, volt=200), REF, False)[0]
    achado = {"tipo": a.tipo, "origem": a.origem, "taxa_ref": a.taxa_ref, "taxa_atual": a.taxa_atual, "eleg_ref": a.n_ref, "eleg_atual": a.n_atual, "z": a.z,
              "resumo": a.resumo, "sinais": [{"camada": s.camada, "etapa": s.etapa, "antes": s.antes, "agora": s.agora, "unidade": s.unidade, "suspeito": s.suspeito} for s in a.sinais]}
    return {"cenario": c, "achado": achado, "apontada": a.origem, "ok": True, "gate_falhas": [("Conversas do Brasil (silver)", "11621", "4684")], "gate_n": 1}


def test_relatorio_pdf_e_gerado(tmp_path):
    caminho = tmp_path / "r.pdf"
    controle = {"cenario": CATALOGO["controle_sem_defeito"], "achado": None, "apontada": "sem alerta", "ok": True, "gate_falhas": [], "gate_n": 0}
    relatorio_pdf.gerar([_resultado("bronze_sem_endereco"), controle], str(caminho))
    dados = caminho.read_bytes()
    assert dados.startswith(b"%PDF") and len(dados) > 4000
