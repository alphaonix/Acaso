"""API do dashboard (FastAPI). Le SOMENTE gold e ops, com usuario somente leitura. Contrato em docs/arquitetura.md.

Publico:    GET /api/saude · POST /api/auth/login · POST /api/auth/logout
Protegido (cookie de sessao; todos aceitam ?pais=, padrao Brazil):
  GET /api/auth/me · /api/paises · /api/catalogo · /api/retencao/resumo · /api/retencao/coortes
  GET /api/retencao/fatores · /api/retencao/curva · /api/retencao/estratos · /api/efeitos · /api/qualidade
  GET /api/explorar/concentracao · /api/explorar/uso-hora · /api/explorar/modelos
"""
import json
import logging
import sys
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from pydantic import BaseModel

from . import seguranca
from .decomposicao import decompor
from .db import consulta

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger("api")
app = FastAPI(title="Retenção do assistente: API", version="0.2.0")
limite = seguranca.LimiteTentativas()


def evento(**campos) -> None:
    log.info(json.dumps(campos, ensure_ascii=False, default=str))


@app.middleware("http")
async def registrar_requisicao(request: Request, call_next):
    """Um log JSON por requisicao (id, rota, status, duracao): base para investigar numero errado e medir p95 (secao 4.1)."""
    inicio, rid = time.perf_counter(), uuid.uuid4().hex[:8]
    resposta = await call_next(request)
    resposta.headers["X-Request-Id"] = rid
    evento(evento="requisicao", request_id=rid, metodo=request.method, caminho=request.url.path,
           consulta=str(request.url.query), status=resposta.status_code,
           duracao_ms=round((time.perf_counter() - inicio) * 1000, 1))
    return resposta


def usuario_atual(request: Request) -> dict:
    dados = seguranca.ler_token(request.cookies.get(seguranca.COOKIE, ""))
    if not dados:
        raise HTTPException(401, "Sessão ausente ou expirada")
    return dados


def pais_valido(pais: str = Query("Brazil")) -> str:
    if not consulta("SELECT 1 FROM gold.pais WHERE pais = %s", (pais,)):
        raise HTTPException(404, f"País sem dados: {pais}")
    return pais


# ---- publico ----------------------------------------------------------------------------------------
@app.get("/api/saude")
def saude() -> dict:
    ultima = consulta("SELECT id, status, finalizado_em, linhas_carregadas FROM ops.etl_execucao ORDER BY id DESC LIMIT 1")
    return {"status": "ok", "ultima_execucao_etl": ultima[0] if ultima else None}


class Credenciais(BaseModel):
    email: str
    senha: str


@app.post("/api/auth/login")
def login(c: Credenciais, request: Request, resposta: Response) -> dict:
    email = c.email.strip().lower()
    chave = f"{request.client.host if request.client else '?'}|{email}"
    if limite.bloqueado(chave):
        evento(evento="login_bloqueado", email=email)
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    linha = consulta("SELECT email, nome, senha_hash FROM ops.usuario_dashboard WHERE lower(email) = %s", (email,))
    ok = seguranca.verificar_senha(c.senha, linha[0]["senha_hash"] if linha else None)
    if not ok:
        limite.registrar_falha(chave)
        evento(evento="login_falhou", email=email)
        raise HTTPException(401, "E-mail ou senha incorretos")
    limite.limpar(chave)
    resposta.set_cookie(seguranca.COOKIE, seguranca.criar_token(linha[0]["email"], linha[0]["nome"]),
                        max_age=seguranca.EXPIRA_S, httponly=True, samesite="lax", secure=seguranca.COOKIE_SEGURO, path="/")
    evento(evento="login_ok", email=email)
    return {"email": linha[0]["email"], "nome": linha[0]["nome"]}


@app.post("/api/auth/logout")
def logout(resposta: Response) -> dict:
    resposta.delete_cookie(seguranca.COOKIE, path="/")
    return {"ok": True}


# ---- protegido --------------------------------------------------------------------------------------
@app.get("/api/auth/me")
def eu(u: dict = Depends(usuario_atual)) -> dict:
    return {"email": u["sub"], "nome": u["nome"]}


@app.get("/api/paises", dependencies=[Depends(usuario_atual)])
def paises() -> list[dict]:
    return consulta("""SELECT pais, nome_exibicao, iso2, fuso, fuso_aproximado, idioma_padrao, tem_texto, usuarios,
                              usuarios_elegiveis, conversas, primeira_data, ultima_data
                       FROM gold.pais ORDER BY usuarios DESC""")


@app.get("/api/catalogo", dependencies=[Depends(usuario_atual)])
def catalogo() -> list[dict]:
    return consulta("SELECT * FROM gold.catalogo_indicador ORDER BY indicador_id")


@app.get("/api/retencao/resumo", dependencies=[Depends(usuario_atual)])
def resumo(pais: str = Depends(pais_valido)) -> dict:
    return consulta("""SELECT sum(novos)::int AS novos, sum(elegiveis)::int AS elegiveis, sum(voltaram_7d)::int AS voltaram_7d,
         CASE WHEN sum(elegiveis) >= 30 THEN sum(voltaram_7d)::numeric / sum(elegiveis) END AS taxa,
         CASE WHEN sum(elegiveis) >= 30 THEN gold.wilson_lo(sum(voltaram_7d), sum(elegiveis)) END AS ic_lo,
         CASE WHEN sum(elegiveis) >= 30 THEN gold.wilson_hi(sum(voltaram_7d), sum(elegiveis)) END AS ic_hi,
         (SELECT min(semana) FROM gold.agg_retorno_semana WHERE pais = %s) AS primeira_semana,
         (SELECT max(semana) FROM gold.agg_retorno_semana WHERE pais = %s) AS ultima_semana
       FROM gold.agg_retorno_semana WHERE pais = %s""", (pais, pais, pais))[0] | _resumo_pais(pais) | _recusa(pais)


def _resumo_pais(pais: str) -> dict:
    """Conversas, turnos da 1a conversa e participacao do GPT-4 (gold.pais) para os cartoes da Visao geral."""
    return consulta("SELECT conversas, turnos_medios, turnos_mediana, pct_gpt4 FROM gold.pais WHERE pais = %s", (pais,))[0]


def _recusa(pais: str) -> dict:
    """Taxa de recusa na 1a resposta (usuarios elegiveis). Vem de gold.agg_retorno_fator (fator 'recusa'); so existe onde ha texto."""
    r = consulta("""SELECT sum(elegiveis) FILTER (WHERE nivel = 'Com recusa')::int AS com, sum(elegiveis)::int AS total
                    FROM gold.agg_retorno_fator WHERE pais = %s AND fator = 'recusa'""", (pais,))[0]
    total = r["total"]; com = (r["com"] or 0) if total is not None else None
    ok = total is not None and total >= 30
    ic = consulta("SELECT gold.wilson_lo(%s, %s) AS lo, gold.wilson_hi(%s, %s) AS hi", (com, total, com, total))[0] if ok else {"lo": None, "hi": None}
    return {"recusa_usuarios": com, "recusa_elegiveis": total, "recusa_taxa": (com / total) if ok else None,
            "recusa_ic_lo": ic["lo"], "recusa_ic_hi": ic["hi"]}


@app.get("/api/retencao/coortes", dependencies=[Depends(usuario_atual)])
def coortes(pais: str = Depends(pais_valido), inicio: str | None = None, fim: str | None = None) -> list[dict]:
    return consulta("""SELECT semana, novos, elegiveis, voltaram_7d, taxa, ic_lo, ic_hi, (taxa IS NULL) AS amostra_pequena
       FROM gold.agg_retorno_semana
       WHERE pais = %s AND semana >= coalesce(%s::date, '0001-01-01') AND semana <= coalesce(%s::date, '9999-12-31')
       ORDER BY semana""", (pais, inicio, fim))


@app.get("/api/retencao/fatores", dependencies=[Depends(usuario_atual)])
def fatores(pais: str = Depends(pais_valido), fator: str | None = None) -> list[dict]:
    return consulta("""SELECT fator, nivel, elegiveis, voltaram_7d, taxa, ic_lo, ic_hi, (taxa IS NULL) AS amostra_pequena
       FROM gold.agg_retorno_fator WHERE pais = %s AND (%s::text IS NULL OR fator = %s)
       ORDER BY fator, elegiveis DESC""", (pais, fator, fator))


@app.get("/api/retencao/comparacao", dependencies=[Depends(usuario_atual)])
def comparacao() -> dict:
    """Retorno em 7 dias de cada pais (somando as semanas) e a media geral (todos os usuarios elegiveis de todos os paises,
    ponderada por usuarios), cada um com intervalo de confianca de Wilson. So paises com 30 ou mais elegiveis."""
    def com_taxa(r: dict) -> dict:
        return {**r, "taxa": r["voltaram_7d"] / r["elegiveis"]}
    paises = consulta("""SELECT pais, sum(elegiveis)::int AS elegiveis, sum(voltaram_7d)::int AS voltaram_7d,
                gold.wilson_lo(sum(voltaram_7d), sum(elegiveis)) AS ic_lo, gold.wilson_hi(sum(voltaram_7d), sum(elegiveis)) AS ic_hi
         FROM gold.agg_retorno_semana GROUP BY pais HAVING sum(elegiveis) >= 30 ORDER BY sum(elegiveis) DESC""")
    geral = consulta("""SELECT sum(elegiveis)::int AS elegiveis, sum(voltaram_7d)::int AS voltaram_7d,
                gold.wilson_lo(sum(voltaram_7d), sum(elegiveis)) AS ic_lo, gold.wilson_hi(sum(voltaram_7d), sum(elegiveis)) AS ic_hi
         FROM gold.agg_retorno_semana""")[0]
    return {"paises": [com_taxa(p) for p in paises], "geral": com_taxa(geral)}

@app.get("/api/uso/diario", dependencies=[Depends(usuario_atual)])
def uso_diario(pais: str = Depends(pais_valido)) -> list[dict]:
    """Conversas e usuarios distintos por dia (fuso do pais). gold.agg_uso_dia."""
    return consulta("SELECT dia, conversas, usuarios_ativos FROM gold.agg_uso_dia WHERE pais = %s ORDER BY dia", (pais,))


FATORES_DECOMPOSICAO = ("modelo", "turnos_da_primeira_conversa", "periodo_do_dia", "tema")
AMOSTRA_MINIMA_MES = 30   # mesmo minimo do resto do dashboard (definicoes.py do ETL)


@app.get("/api/retencao/decomposicao", dependencies=[Depends(usuario_atual)])
def decomposicao(pais: str = Depends(pais_valido), fator: str = "modelo", de: str | None = None, para: str | None = None) -> dict:
    """Por que o retorno mudou entre dois meses? Decomposicao shift-share (mix x taxa x interacao) pelo perfil `fator`.
      R = soma_k w_k r_k   (w = peso do nivel k entre os elegiveis; r = taxa de retorno do nivel)
      mix       = soma (w1 - w0) r0     -> mudou QUEM chegou
      taxa      = soma w0 (r1 - r0)     -> mudou o retorno DENTRO de cada perfil
      interacao = soma (w1 - w0)(r1 - r0)
    As tres somam exatamente R1 - R0 (`soma_confere`). Nivel ausente num mes usa a taxa geral do mes (peso zero)."""
    if fator not in FATORES_DECOMPOSICAO:
        raise HTTPException(400, f"fator deve ser um de {', '.join(FATORES_DECOMPOSICAO)}")
    linhas = consulta("SELECT mes, nivel, elegiveis, voltaram_7d FROM gold.agg_retorno_mes_fator WHERE pais = %s AND fator = %s",
                      (pais, fator))
    por_mes: dict[str, dict[str, tuple[int, int]]] = {}
    for r in linhas:
        por_mes.setdefault(str(r["mes"]), {})[r["nivel"]] = (r["elegiveis"], r["voltaram_7d"])
    tot = {m: (sum(n for n, _ in d.values()), sum(v for _, v in d.values())) for m, d in por_mes.items()}
    ok = sorted(m for m, (n, _) in tot.items() if n >= AMOSTRA_MINIMA_MES)
    meses = [{"mes": m, "elegiveis": tot[m][0], "taxa": tot[m][1] / tot[m][0]} for m in ok]
    if len(ok) < 2:
        return {"disponivel": False, "fator": fator, "meses": meses}
    if de is None or para is None:        # padrao: o par de meses consecutivos com a maior variacao
        i = max(range(1, len(ok)), key=lambda k: abs(tot[ok[k]][1] / tot[ok[k]][0] - tot[ok[k - 1]][1] / tot[ok[k - 1]][0]))
        de, para = ok[i - 1], ok[i]
    if de not in ok or para not in ok or de == para:
        raise HTTPException(400, "periodos invalidos ou com amostra pequena")
    return {"disponivel": True, "fator": fator, "de": de, "para": para, "meses": meses, **decompor(por_mes, de, para)}

def _com_taxa(r: dict, num: str, den: str) -> dict:
    """Taxa e IC de Wilson de uma linha; com menos de 30 no denominador a taxa fica nula (amostra pequena)."""
    n, x = r[den], r[num]
    if n is None or n < AMOSTRA_MINIMA_MES:
        return {**r, "taxa": None, "ic_lo": None, "ic_hi": None, "amostra_pequena": True}
    ic = consulta("SELECT gold.wilson_lo(%s, %s) AS lo, gold.wilson_hi(%s, %s) AS hi", (x, n, x, n))[0]
    return {**r, "taxa": x / n, "ic_lo": ic["lo"], "ic_hi": ic["hi"], "amostra_pequena": False}


@app.get("/api/retencao/curva", dependencies=[Depends(usuario_atual)])
def curva(pais: str = Depends(pais_valido)) -> dict:
    """Curva de retorno: % de usuarios que voltaram em ate d dias, entre quem tem 30 dias de janela completa (gold.agg_curva_retorno).
    `voltou_24h` = ponto d = 1; `voltou_7d` = d = 7 (nesta base, por isso difere do indicador principal)."""
    pontos = [_com_taxa(r, "voltaram", "usuarios") for r in
              consulta("SELECT dias::float AS dias, usuarios, voltaram FROM gold.agg_curva_retorno WHERE pais = %s ORDER BY dias", (pais,))]
    por_dia = {p["dias"]: p for p in pontos}
    return {"pontos": pontos, "voltou_24h": por_dia.get(1.0), "voltou_7d": por_dia.get(7.0), "voltou_30d": por_dia.get(30.0)}


@app.get("/api/retencao/estratos", dependencies=[Depends(usuario_atual)])
def estratos(pais: str = Depends(pais_valido)) -> list[dict]:
    """Saudacao e recusa DENTRO de cada familia de modelo (GPT-4 e GPT-3.5): taxa por nivel e a diferenca simples
    (grupo 'tratado' menos grupo de comparacao, em pontos percentuais, IC de 95% pela aproximacao normal). Sem ajuste: e hipotese."""
    linhas = consulta("""SELECT fator, familia, nivel, elegiveis, voltaram_7d AS voltaram FROM gold.agg_estrato WHERE pais = %s
                         ORDER BY fator, familia, nivel""", (pais,))
    tratado = {"recusa": "Com recusa", "saudacao": "Saudação"}
    grupos: dict[tuple[str, str], dict[str, dict]] = {}
    for r in linhas:
        grupos.setdefault((r["fator"], r["familia"]), {})[r["nivel"]] = _com_taxa(r, "voltaram", "elegiveis")
    saida = []
    for (fator, familia), niveis in grupos.items():
        t = niveis.get(tratado[fator])
        c = next((v for k, v in niveis.items() if k != tratado[fator]), None)
        dif = None
        if t and c and not t["amostra_pequena"] and not c["amostra_pequena"]:
            d = t["taxa"] - c["taxa"]
            ep = (t["taxa"] * (1 - t["taxa"]) / t["elegiveis"] + c["taxa"] * (1 - c["taxa"]) / c["elegiveis"]) ** 0.5
            dif = {"pp": d * 100, "ic_lo": (d - 1.96 * ep) * 100, "ic_hi": (d + 1.96 * ep) * 100}
        saida.append({"fator": fator, "familia": familia, "tratado": t, "comparacao": c, "diferenca": dif})
    return saida


@app.get("/api/explorar/concentracao", dependencies=[Depends(usuario_atual)])
def concentracao(pais: str = Depends(pais_valido)) -> dict:
    """Quantas conversas cada pessoa tem: faixas (1, 2-3, 4-10, 11+), participacao no volume e peso dos 10 mais ativos."""
    faixas = consulta("SELECT faixa, usuarios, conversas FROM gold.agg_concentracao WHERE pais = %s ORDER BY ordem", (pais,))
    tu, tc = sum(f["usuarios"] for f in faixas), sum(f["conversas"] for f in faixas)
    for f in faixas:
        f["pct_pessoas"], f["pct_conversas"] = f["usuarios"] / tu, f["conversas"] / tc
    p = consulta("SELECT usuarios, top10_pct, maior_pct, pessoas_1_conversa_pct FROM gold.pais WHERE pais = %s", (pais,))[0]
    ok = p["usuarios"] >= AMOSTRA_MINIMA_MES
    return {"faixas": faixas if ok else [], "usuarios": tu, "conversas": tc,
            "top10_pct": p["top10_pct"] if ok else None, "maior_pct": p["maior_pct"] if ok else None,
            "pessoas_1_conversa_pct": p["pessoas_1_conversa_pct"] if ok else None}


@app.get("/api/explorar/uso-hora", dependencies=[Depends(usuario_atual)])
def uso_hora(pais: str = Depends(pais_valido)) -> dict:
    """Conversas por dia da semana (1=segunda ... 7=domingo) e hora, no fuso do pais, e a parcela no expediente (seg-sex, 9h-18h)."""
    celulas = consulta("SELECT dia_semana, hora, conversas FROM gold.agg_uso_hora WHERE pais = %s ORDER BY dia_semana, hora", (pais,))
    total = sum(c["conversas"] for c in celulas)
    exp = sum(c["conversas"] for c in celulas if c["dia_semana"] <= 5 and 9 <= c["hora"] < 18)
    noite = sum(c["conversas"] for c in celulas if c["hora"] >= 22 or c["hora"] < 6)
    fuso = consulta("SELECT fuso, fuso_aproximado FROM gold.pais WHERE pais = %s", (pais,))[0]
    return {"celulas": celulas, "total": total, "pct_expediente": exp / total if total else None,
            "pct_madrugada": noite / total if total else None, **fuso}


@app.get("/api/explorar/modelos", dependencies=[Depends(usuario_atual)])
def modelos(pais: str = Depends(pais_valido)) -> dict:
    """Comparacao entre modelos: por familia (GPT-4 e GPT-3.5) e por versao, o retorno em 7 dias (elegiveis), a recusa na 1a resposta
    (conversas com texto) e o tamanho medio da resposta; mais a participacao do GPT-4 por mes. Taxas com menos de 30 no denominador ficam nulas."""
    meses = consulta("SELECT mes, conversas, conversas_gpt4 FROM gold.agg_modelo_mes WHERE pais = %s ORDER BY mes", (pais,))
    brutas = consulta("""SELECT modelo, conversas, com_recusa, resp_media_chars, elegiveis, voltaram_7d
                         FROM gold.agg_recusa_modelo WHERE pais = %s ORDER BY modelo""", (pais,))
    versoes = []
    for r in brutas:
        v = _com_taxa(r, "com_recusa", "conversas")                       # recusa
        v["recusa"] = {k: v.pop(k) for k in ("taxa", "ic_lo", "ic_hi", "amostra_pequena")}
        v["retorno"] = {k: x for k, x in _com_taxa({"x": r["voltaram_7d"], "n": r["elegiveis"]}, "x", "n").items() if k in ("taxa", "ic_lo", "ic_hi", "amostra_pequena")}
        v["familia"] = "GPT-4" if r["modelo"].startswith("gpt-4") else "GPT-3.5"
        versoes.append(v)
    familias = []
    for nome in ("GPT-3.5", "GPT-4"):
        ret = consulta("SELECT elegiveis, voltaram_7d FROM gold.agg_retorno_fator WHERE pais = %s AND fator = 'modelo' AND nivel = %s", (pais, nome))
        vs = [v for v in versoes if v["familia"] == nome]
        if not ret and not vs:
            continue
        conv, rec = sum(v["conversas"] for v in vs), sum(v["com_recusa"] for v in vs)
        f = {"familia": nome, "elegiveis": ret[0]["elegiveis"] if ret else 0, "voltaram_7d": ret[0]["voltaram_7d"] if ret else 0,
             "conversas": conv, "com_recusa": rec}
        f["retorno"] = {k: x for k, x in _com_taxa({"x": f["voltaram_7d"], "n": f["elegiveis"]}, "x", "n").items() if k in ("taxa", "ic_lo", "ic_hi", "amostra_pequena")}
        f["recusa"] = {k: x for k, x in _com_taxa({"x": rec, "n": conv}, "x", "n").items() if k in ("taxa", "ic_lo", "ic_hi", "amostra_pequena")} if conv else None
        familias.append(f)
    return {"meses": meses, "versoes": versoes, "familias": familias}


@app.get("/api/efeitos", dependencies=[Depends(usuario_atual)])
def efeitos(pais: str = Depends(pais_valido)) -> list[dict]:
    return consulta("SELECT * FROM gold.efeito_fator WHERE pais = %s ORDER BY abs(efeito_pp) DESC", (pais,))


@app.get("/api/qualidade", dependencies=[Depends(usuario_atual)])
def qualidade() -> dict:
    ex = consulta("SELECT id, status, iniciado_em, finalizado_em, versao_codigo, linhas_lidas, linhas_carregadas "
                  "FROM ops.etl_execucao ORDER BY id DESC LIMIT 1")
    if not ex:
        return {"execucao": None, "verificacoes": [], "lotes": []}
    eid = ex[0]["id"]
    return {"execucao": ex[0],
            "verificacoes": consulta("SELECT verificacao, esperado, obtido, passou FROM ops.qa_resultado WHERE execucao_id = %s ORDER BY id", (eid,)),
            "lotes": consulta("SELECT arquivo, sha256, linhas FROM ops.bronze_lote WHERE execucao_id = %s ORDER BY id", (eid,)),
            "problemas": consulta("SELECT codigo, escopo, afetadas, total FROM gold.problema_qualidade ORDER BY ordem")}
