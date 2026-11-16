"""RECARGA: o banco guarda os dados entre um `docker compose up` e outro, entao o ETL so recarrega quando precisa:
  - a recarga foi pedida (`--recarregar`);
  - o banco ainda nao tem carga bem-sucedida;
  - a semente mudou desde a ultima carga (sha256 diferente).
Sem isso, o segundo `up` sai na hora e a API sobe com os dados que ja estao la.
"""
from camadas import bronze
from camadas.bronze.carregar import DESTINOS
from main import carga_necessaria


def _semente(tmp_path, conteudo=b"a"):
    for i, nome in enumerate(DESTINOS):
        (tmp_path / nome).write_bytes(conteudo + bytes([i]))
    return tmp_path


def _carga(dw, semente, status="ok"):
    """Registra uma execucao e os lotes que ela leu, como o ETL faz."""
    exec_id = dw.execute("INSERT INTO ops.etl_execucao (versao_codigo, status) VALUES ('teste', %s) RETURNING id", (status,)).fetchone()[0]
    for nome, sha in bronze.impressao_da_semente(semente).items():
        dw.execute("INSERT INTO ops.bronze_lote (execucao_id, arquivo, sha256, linhas, tamanho_bytes, tabela_destino) VALUES (%s, %s, %s, 1, 1, 'x')",
                   (exec_id, nome, sha))
    return exec_id


def test_banco_sem_carga_precisa_carregar(dw, tmp_path):
    precisa, motivo = carga_necessaria(dw, _semente(tmp_path))
    assert precisa and "ainda nao tem carga" in motivo


def test_mesma_semente_e_carga_ok_nao_recarrega(dw, tmp_path):
    semente = _semente(tmp_path)
    exec_id = _carga(dw, semente)
    precisa, motivo = carga_necessaria(dw, semente)
    assert not precisa and str(exec_id) in motivo


def test_recarga_pedida_sempre_carrega(dw, tmp_path):
    semente = _semente(tmp_path)
    _carga(dw, semente)
    precisa, motivo = carga_necessaria(dw, semente, forcar=True)
    assert precisa and "pedida" in motivo


def test_semente_diferente_recarrega(dw, tmp_path):
    _carga(dw, _semente(tmp_path, b"a"))
    precisa, motivo = carga_necessaria(dw, _semente(tmp_path, b"b"))      # sobrescreve os arquivos: outro sha256
    assert precisa and "semente mudou" in motivo


def test_carga_que_falhou_nao_conta(dw, tmp_path):
    semente = _semente(tmp_path)
    _carga(dw, semente, status="falhou")
    precisa, motivo = carga_necessaria(dw, semente)
    assert precisa and "ainda nao tem carga" in motivo


def test_so_vale_a_ultima_carga_bem_sucedida(dw, tmp_path):
    antiga = _semente(tmp_path, b"a")
    _carga(dw, antiga)
    nova = _semente(tmp_path, b"b")
    _carga(dw, nova)
    assert carga_necessaria(dw, nova)[0] is False       # a ultima carga ok leu a semente atual
