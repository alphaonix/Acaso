"""O PDF da anomalia so existe quando ha anomalia: carga normal nao gera arquivo; carga retida gera, com a camada provavel e a amostra de pessoas."""
import json

import main
from comum import relatorio_anomalia


def _exec(dw, status="rodando"):
    return dw.execute("INSERT INTO ops.etl_execucao (versao_codigo, status) VALUES ('teste', %s) RETURNING id", (status,)).fetchone()[0]


def _pessoas(dw):
    dw.execute("INSERT INTO silver.dim_pais (pais, nome_exibicao, fuso, fuso_aproximado, tem_texto) VALUES ('Brazil', 'Brasil', 'America/Sao_Paulo', true, true) ON CONFLICT DO NOTHING")
    dw.execute("""INSERT INTO silver.fato_usuario (usuario_id, pais, primeira_vez_utc, semana, hora, dia_semana, modelo, turnos, convs_1a_sessao, convs_total, voltou_7d, elegivel)
                  VALUES ('abc123', 'Brazil', now(), date '2023-11-20', 10, 1, 'gpt-4', 1, 1, 5, true, true)""")


def _anomalia(dw, exec_id):
    ref = _exec(dw, "ok")
    dw.execute("""INSERT INTO auditoria.anomalia (execucao_id, execucao_referencia, pais, taxa_referencia, taxa_atual, elegiveis_referencia, elegiveis_atual, z, origem, resumo, tipo, sinais)
                  VALUES (%s, %s, 'Brazil', 0.25, 0.97, 2000, 2000, 30, 'TRANSFORMACAO', 'uma regra mudou', 'TAXA', %s)""",
               (exec_id, ref, json.dumps([{"camada": "silver", "etapa": "elegiveis entre as pessoas", "antes": 0.9, "agora": 0.3, "unidade": "%", "suspeito": True}])))


def test_sem_anomalia_nao_gera_arquivo(dw, tmp_path):
    assert relatorio_anomalia.gerar(dw, dw, _exec(dw), "ok", str(tmp_path)) is None
    assert list(tmp_path.iterdir()) == []


def test_com_anomalia_gera_o_pdf_com_o_numero_da_carga(dw, tmp_path):
    e = _exec(dw)
    _pessoas(dw)
    _anomalia(dw, e)
    caminho = relatorio_anomalia.gerar(dw, dw, e, "retida", str(tmp_path))
    assert caminho.endswith(f"relatorio_anomalia_carga_{e}.pdf")
    assert open(caminho, "rb").read(5) == b"%PDF-"


def test_o_alerta_semanal_tambem_gera_o_pdf(dw, tmp_path):
    e = _exec(dw)
    _pessoas(dw)
    dw.execute("""INSERT INTO auditoria.anomalia_semanal (execucao_id, pais, semana, diagnostico, camada, novos, novos_base, voltaram, voltaram_base, taxa, taxa_base, resumo, nova)
                  VALUES (%s, 'Brazil', date '2023-11-20', 'PESSOA_DIVIDIDA', 'SILVER_OU_BRONZE', 80, 40, 20, 20, 0.2, 0.5, 'novos dobraram', true)""", (e,))
    assert relatorio_anomalia.gerar(dw, dw, e, "retida", str(tmp_path)) is not None


def test_falha_ao_gerar_o_pdf_nao_derruba_a_carga(dw, monkeypatch, capsys):
    def quebra(*a, **k):
        raise OSError("disco cheio")
    monkeypatch.setattr(main.relatorio_anomalia, "gerar", quebra)
    main.relatorio_pdf(dw, dw, _exec(dw), "retida")              # nao levanta
    assert "nao foi possivel gerar o relatorio" in capsys.readouterr().out


def test_a_simulacao_nao_gera_o_pdf_da_carga(dw, monkeypatch):
    monkeypatch.setenv("ETL_SEM_PDF", "1")
    monkeypatch.setattr(main.relatorio_anomalia, "gerar", lambda *a, **k: (_ for _ in ()).throw(AssertionError("nao devia gerar")))
    main.relatorio_pdf(dw, dw, _exec(dw), "retida")