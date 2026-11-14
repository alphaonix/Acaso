"""Monta conversas sinteticas na bronze, roda a silver (e a gold) e devolve o que os testes querem conferir.
Os testes usam o Brasil e duas ANCORAS (2023-01-01 e 2023-12-31) que fixam o periodo dos dados: a elegibilidade depende dele."""
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from camadas import gold, silver

UTC = timezone.utc
UA_CHROME_119 = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
UA_CHROME_120 = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
UA_FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
UA_ANDROID = "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"
INICIO_DADOS = "2023-01-01 10:00"
FIM_DADOS = "2023-12-31 10:00"


def t(texto: str) -> datetime:
    """'2023-06-01 10:00' (UTC) -> datetime"""
    return datetime.fromisoformat(texto).replace(tzinfo=UTC)


@dataclass
class C:
    """Uma conversa. `inicio` = 1a resposta do assistente; `fim` = ultimo turno (padrao: 5 min depois do inicio)."""
    ip: str | None
    inicio: datetime | None
    fim: datetime | None = None
    ua: str | None = UA_CHROME_119
    pais: str | None = "Brazil"
    hash: str | None = None
    modelo: str = "gpt-3.5-turbo"
    turnos: int = 1
    idioma: str = "Portuguese"
    estado: str | None = "São Paulo"
    prompt: str = "Explique o que é fotossíntese"
    resposta: str = "Fotossíntese é o processo em que as plantas produzem energia a partir da luz."
    extras: dict = field(default_factory=dict)


def uid(ip: str, normalizado: str = "Chrome/Windows") -> str:
    """usuario_id esperado: os 12 primeiros caracteres do md5(ip|navegador/sistema) (BDR-001)."""
    return hashlib.md5(f"{ip}|{normalizado}".encode()).hexdigest()[:12]


def inserir(dw, convs: list[C]) -> None:
    with dw.cursor() as cur:
        for i, c in enumerate(convs):
            fim = c.fim or (c.inicio + timedelta(minutes=5) if c.inicio else None)
            conversa = Jsonb([{"role": "user", "content": c.prompt, "timestamp": None},
                              {"role": "assistant", "content": c.resposta, "timestamp": c.inicio.isoformat() if c.inicio else None}])
            cur.execute(
                """INSERT INTO bronze.wildchat (conversation_hash, model, "timestamp", turn, language, country, state, hashed_ip, header,
                                                toxic, redacted, conversation, primeira_resposta_ts, arquivo_origem)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, false, false, %s, %s, 'teste')""",
                (c.hash or f"h{i}", c.modelo, fim, c.turnos, c.idioma, c.pais, c.estado, c.ip, Jsonb({"user-agent": c.ua, **({"accept-language": c.extras["al"]} if "al" in c.extras else {})}),
                 conversa if c.pais == "Brazil" else None, c.inicio))


def rodar(dw, convs: list[C], com_gold: bool = False) -> None:
    """Insere as conversas (mais as ancoras) na bronze e roda a silver (e, se pedido, a gold)."""
    ancoras = [C("ancora-ini", t(INICIO_DADOS)), C("ancora-fim", t(FIM_DADOS))]
    inserir(dw, ancoras + convs)
    silver.construir_silver(dw)
    if com_gold:
        gold.construir_gold(dw)


def linhas(dw, sql: str, params=None) -> list[tuple]:
    with dw.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def usuario(dw, ip: str, normalizado: str = "Chrome/Windows") -> dict:
    """Linha de silver.fato_usuario do usuario (como dicionario)."""
    with dw.cursor() as cur:
        cur.execute("SELECT * FROM silver.fato_usuario WHERE usuario_id = %s", (uid(ip, normalizado),))
        cols = [d.name for d in cur.description]
        r = cur.fetchone()
        assert r is not None, f"usuario nao encontrado: {ip} ({normalizado})"
        return dict(zip(cols, r))