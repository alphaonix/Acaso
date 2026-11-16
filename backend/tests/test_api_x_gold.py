"""Teste de integracao: o que a API devolve = o que esta na gold (e as camadas batem entre si).

Precisa do banco ja carregado pelo ETL. Sem DATABASE_URL_ETL (usuario do ETL, que enxerga todas as camadas) os testes sao pulados,
para que `testes-api` continue rodando sem banco. Rode com: docker compose --profile test run --rm testes-integracao"""
import os

import psycopg
import pytest
from psycopg.rows import dict_row

if not os.environ.get("DATABASE_URL_ETL") or not os.environ.get("DATABASE_URL"):
    pytest.skip("sem banco (defina DATABASE_URL e DATABASE_URL_ETL)", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app import seguranca  # noqa: E402
from app.main import app  # noqa: E402
from tests import conciliacao as cc  # noqa: E402


@pytest.fixture(scope="module")
def db():
    with psycopg.connect(os.environ["DATABASE_URL_ETL"], row_factory=dict_row, autocommit=True) as con:
        yield con


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.cookies.set(seguranca.COOKIE, seguranca.criar_token("teste@local", "Teste"))
        yield c


@pytest.fixture(scope="module")
def sem_cookie():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def checks(client, db, sem_cookie):
    return cc.Conciliador(client, db).todos(cc.paises_de_teste(db), sem_cookie)


def _grupo(checks, g):
    return [c for c in checks if c.grupo == g]


def _falhas(cs):
    return [f"[{c.pais or 'todos'}] {c.descricao}: esperado={c.esperado!r} obtido={c.obtido!r} {c.detalhe}" for c in cs if not c.ok]


@pytest.mark.parametrize("grupo", ["paises", "resumo", "coortes", "meses", "fatores", "comparacao", "curva", "estratos", "modelos", "concentracao",
                                   "uso_hora", "uso_diario", "efeitos", "decomposicao", "catalogo", "qualidade", "seguranca"])
def test_api_igual_gold(checks, grupo):
    cs = _grupo(checks, grupo)
    assert cs, f"nenhuma conferencia do grupo {grupo}"
    assert not _falhas(cs), "\n".join(_falhas(cs))


def test_camadas_batem_entre_si(db):
    cs = cc.camadas(db)
    assert len(cs) >= 14
    assert not _falhas(cs), "\n".join(_falhas(cs))


def test_numero_principal_do_brasil(client):
    """O numero que abre o dashboard: 2.234 elegiveis, 530 voltaram, 23,72%."""
    a = client.get("/api/retencao/resumo", params={"pais": "Brazil"}).json()
    assert (a["elegiveis"], a["voltaram_7d"]) == (2234, 530)
    assert round(a["taxa"] * 100, 2) == 23.72


def test_resposta_traz_rastreio(client, db):
    """Cada resposta diz de qual carga vem o numero e qual versao da definicao o calculou (investigar um numero errado depois)."""
    r = client.get("/api/retencao/resumo", params={"pais": "Brazil"})
    carga = db.execute("SELECT max(id) AS id FROM ops.etl_execucao WHERE status IN ('ok', 'alerta')").fetchone()["id"]
    assert r.headers["X-Carga-Id"] == str(carga)
    assert r.headers["X-Versao-Definicao"] == "retorno_7d@v1"
    assert len(r.headers["X-Request-Id"]) == 8


def test_erro_plantado_e_detectado(client, db):
    """Prova que a conciliacao nao e decorativa: um numero errado de proposito tem de aparecer como divergencia."""
    c = cc.Conciliador(client, db)
    c.ver("plantado", "Brazil", "numero errado de proposito", 2235, client.get("/api/retencao/resumo", params={"pais": "Brazil"}).json()["elegiveis"])
    assert not c.checks[0].ok
