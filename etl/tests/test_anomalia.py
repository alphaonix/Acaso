"""ANOMALIA: a taxa de um pais salta (25% -> 97%) e o sistema aponta ONDE comecou: bronze (fonte), silver, gold ou transformacao (codigo)."""
import pytest

from comum import anomalia, diagnostico
from comum.diagnostico import Metrica


def medidas(pais="Brazil", linhas=10000, ips=4000, nulos_ip=0, nulos_ini=0, nulos_ua=0, conv=9990, pessoas=3000, eleg=2000, volt=500, g_eleg=None, g_volt=None):
    """Medidas de UM pais no formato do historico (auditoria.metrica), no estado 'normal' por padrao."""
    b = "(vazio)" if pais == "Desconhecido" else pais
    return {("bronze", "linhas_por_pais", b): linhas, ("bronze", "ips_distintos_por_pais", b): ips,
            ("bronze", "nulos_por_pais", f"{b}|hashed_ip"): nulos_ip, ("bronze", "nulos_por_pais", f"{b}|inicio"): nulos_ini,
            ("bronze", "nulos_por_pais", f"{b}|user_agent"): nulos_ua,
            ("silver", "conversas", pais): conv, ("silver", "pessoas", pais): pessoas, ("silver", "pessoas_elegiveis", pais): eleg, ("silver", "voltaram_7d", pais): volt,
            ("gold", "pais_elegiveis", pais): eleg if g_eleg is None else g_eleg, ("gold", "pais_voltaram", pais): volt if g_volt is None else g_volt}


REF = medidas()                                  # 500 de 2.000 = 25%


def _origem(atual, mesma=False, ref=REF):
    achadas = anomalia.detectar(atual, ref, mesma)
    assert len(achadas) == 1, achadas
    return achadas[0]


def test_carga_igual_nao_e_anomalia():
    assert anomalia.detectar(REF, REF, True) == []


def test_variacao_pequena_nao_e_anomalia():
    assert anomalia.detectar(medidas(volt=520), REF, False) == []          # 25% -> 26%


def test_variacao_grande_mas_amostra_pequena_nao_e_avaliada():
    assert anomalia.detectar(medidas(eleg=20, volt=19), medidas(eleg=20, volt=5), False) == []   # menos de 30 elegiveis: nao se avalia


def test_salto_de_25_para_97_por_cento_e_detectado():
    a = _origem(medidas(eleg=2000, volt=1940))
    assert a.pais == "Brazil" and round(a.taxa_ref, 2) == 0.25 and round(a.taxa_atual, 2) == 0.97 and a.z > 40


def test_queda_tambem_e_detectada():
    assert _origem(medidas(volt=100)).taxa_atual == 0.05


def test_origem_gold_quando_a_gold_nao_bate_com_a_silver():
    a = _origem(medidas(volt=500, g_volt=1500))
    assert a.origem == "GOLD"


def test_origem_transformacao_quando_a_entrada_e_identica():
    a = _origem(medidas(eleg=700, volt=500), mesma=True)
    assert a.origem == "TRANSFORMACAO" and "identicos" in a.resumo


def test_origem_bronze_quando_a_fonte_mudou_de_padrao():
    """60% das linhas chegam sem endereco: menos pessoas elegiveis, taxa sobe. O defeito nasceu na entrada."""
    a = _origem(medidas(nulos_ip=6000, ips=1500, conv=4000, pessoas=1200, eleg=700, volt=500))
    assert a.origem == "BRONZE"
    assert any(s.camada == "bronze" and s.suspeito and "sem endereco" in s.etapa for s in a.sinais)


def test_origem_silver_quando_a_entrada_e_normal_e_a_limpeza_muda():
    """Bronze igual; a silver passa a descartar 40% das conversas: o defeito esta na limpeza."""
    a = _origem(medidas(conv=6000, pessoas=1800, eleg=700, volt=500))
    assert a.origem == "SILVER"
    assert any(s.camada == "silver" and s.suspeito for s in a.sinais) and not any(s.camada == "bronze" and s.suspeito for s in a.sinais)


def test_origem_silver_quando_so_a_elegibilidade_muda():
    a = _origem(medidas(eleg=700, volt=500))          # entrada igual, 70% menos elegiveis
    assert a.origem == "SILVER" and any("elegiveis entre as pessoas" in s.etapa and s.suspeito for s in a.sinais)


def test_sem_causa_tecnica_quando_o_funil_inteiro_esta_estavel():
    """Taxa mudou, mas bronze, limpeza, pessoas e elegiveis estao como antes: pode ser mudanca real de comportamento."""
    a = _origem(medidas(volt=1200))                   # so o numerador sobe
    assert a.origem == "SEM_CAUSA"


def test_pais_desconhecido_liga_bronze_vazio_com_silver_desconhecido():
    ref = medidas("Desconhecido")
    a = _origem(medidas("Desconhecido", nulos_ip=6000, ips=1500, conv=4000, pessoas=1200, eleg=700, volt=500), ref=ref)
    assert a.pais == "Desconhecido" and a.origem == "BRONZE"


def test_relatorio_mostra_o_funil_e_a_origem():
    texto = "\n".join(anomalia.relatorio(_origem(medidas(nulos_ip=6000, ips=1500, conv=4000, pessoas=1200, eleg=700, volt=500))))
    assert "25.0% -> 71.4%" in texto and "ORIGEM PROVAVEL: BRONZE" in texto and "--- BRONZE ---" in texto and "--- SILVER ---" in texto and "--- GOLD ---" in texto
    assert "!! linhas sem endereco" in texto


@pytest.mark.parametrize("camada,esperada", [("bronze", "BRONZE"), ("silver", "SILVER"), ("gold", "GOLD"), ("transformacao", "TRANSFORMACAO")])
def test_simulacao_aponta_a_camada_onde_o_defeito_foi_plantado(camada, esperada):
    ref = medidas()
    atual, mesma = anomalia.simular(ref, "Brazil", camada)
    achadas = anomalia.detectar(atual, ref, mesma)
    assert [a.origem for a in achadas] == [esperada]


# ------------------------------------------------------------------ dentro da carga (com banco)
def _carga(dw, status, sha, m):
    i = dw.execute("INSERT INTO ops.etl_execucao (status) VALUES (%s) RETURNING id", (status,)).fetchone()[0]
    dw.execute("INSERT INTO ops.bronze_lote (execucao_id, arquivo, sha256, linhas, tamanho_bytes, tabela_destino) VALUES (%s, 'x', %s, 1, 1, 'bronze.wildchat')", (i, sha))
    diagnostico.gravar_metricas(dw, i, [Metrica(c, n, e, float(v), None) for (c, n, e), v in m.items()])
    return i


def test_verificar_grava_a_anomalia_com_a_origem(dw):
    _carga(dw, "ok", "s1", REF)
    atual = _carga(dw, "rodando", "s2", medidas(nulos_ip=6000, ips=1500, conv=4000, pessoas=1200, eleg=700, volt=500))
    r = anomalia.verificar(dw, atual)[0]
    assert not r.passou and r.obtido == "1"
    linha = dw.execute("SELECT pais, origem, taxa_referencia, taxa_atual FROM auditoria.anomalia WHERE execucao_id = %s", (atual,)).fetchone()
    assert linha[0] == "Brazil" and linha[1] == "BRONZE" and float(linha[2]) == 0.25


def test_verificar_sem_anomalia_passa_e_sem_carga_anterior_tambem(dw):
    primeira = _carga(dw, "rodando", "s1", REF)
    assert anomalia.verificar(dw, primeira)[0].passou                      # sem carga anterior
    segunda = _carga(dw, "rodando", "s1", REF)
    dw.execute("UPDATE ops.etl_execucao SET status = 'ok' WHERE id = %s", (primeira,))
    assert anomalia.verificar(dw, segunda)[0].passou
