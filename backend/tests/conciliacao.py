"""CONCILIACAO ponta a ponta: confere que cada numero que a API devolve bate com o que esta na gold, e que as camadas batem entre si.

Usado por dois lados: os testes (test_api_x_gold.py) e o relatorio visual (relatorio_fluxo.py). Nada aqui reaproveita o calculo da API:
as taxas e os intervalos de Wilson esperados sao recalculados em Python a partir das CONTAGENS da gold; a API os calcula no Postgres.
Cada conferencia compara linha a linha e conta as divergencias (esperado: 0)."""
import math
from dataclasses import dataclass, field

AMOSTRA_MINIMA = 30


@dataclass
class Check:
    grupo: str            # ex.: resumo, coortes, modelos
    pais: str             # '' quando vale para todos
    descricao: str
    esperado: object
    obtido: object
    ok: bool
    detalhe: str = ""     # as primeiras divergencias, para investigar


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson (95%), recalculado aqui em Python para nao depender da funcao SQL que a API usa."""
    p = k / n
    centro, margem = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centro - margem) / (1 + z * z / n), (centro + margem) / (1 + z * z / n)


def _num(x):
    return float(x) if isinstance(x, (int, float)) or hasattr(x, "as_tuple") else x


def igual(a, b, tol: float = 1e-9) -> bool:
    """Compara valores vindos do JSON (API) e do banco (gold): numeros com tolerancia, datas como texto, vazio com vazio."""
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(_num(a), float) and isinstance(_num(b), float):
        return math.isclose(_num(a), _num(b), rel_tol=tol, abs_tol=tol)
    return str(a) == str(b)


def taxa_ic(k, n):
    """(taxa, ic_lo, ic_hi) esperados; tudo None quando ha menos de 30 no denominador (regra da amostra pequena)."""
    if n is None or n < AMOSTRA_MINIMA:
        return None, None, None
    lo, hi = wilson(k, n)
    return k / n, lo, hi


def paises_de_teste(db) -> list[str]:
    """Brasil, os dois maiores, Portugal, Desconhecido e o menor pais que tem elegiveis mas menos de 30 (testa a regra da amostra pequena)."""
    cur = db.execute("SELECT pais FROM gold.pais ORDER BY usuarios_elegiveis DESC")
    todos = [r["pais"] for r in cur.fetchall()]
    pequeno = db.execute("SELECT pais FROM gold.pais WHERE usuarios_elegiveis BETWEEN 1 AND 29 ORDER BY usuarios_elegiveis, pais LIMIT 1").fetchall()
    escolhidos = ["Brazil"] + todos[:2] + [p for p in ("Portugal", "Desconhecido") if p in todos] + [r["pais"] for r in pequeno]
    return list(dict.fromkeys(escolhidos))


class Conciliador:
    def __init__(self, client, db):
        self.c, self.db, self.checks = client, db, []

    # -- utilidades
    def get(self, url: str, **params):
        r = self.c.get(url, params=params or None)
        assert r.status_code == 200, f"{url} {params} devolveu {r.status_code}: {r.text[:200]}"
        return r.json()

    def gold(self, sql: str, params: tuple = ()) -> list[dict]:
        return self.db.execute(sql, params).fetchall()

    def ver(self, grupo, pais, descricao, esperado, obtido, tol: float = 1e-9, detalhe: str = "") -> Check:
        ch = Check(grupo, pais, descricao, esperado, obtido, igual(esperado, obtido, tol), detalhe)
        self.checks.append(ch)
        return ch

    def linhas(self, grupo, pais, descricao, api: list[dict], gold: list[dict], chave: tuple[str, ...], campos: tuple[str, ...], tol: float = 1e-9) -> Check:
        """Junta pela chave e compara cada campo. Divergencia = linha que so existe de um lado ou campo diferente."""
        k = lambda r: tuple(str(r[c]) for c in chave)
        a, g = {k(r): r for r in api}, {k(r): r for r in gold}
        ruins = []
        for chv in sorted(a.keys() | g.keys()):
            if chv not in a or chv not in g:
                ruins.append(f"{chv}: so existe {'na gold' if chv in g else 'na API'}")
                continue
            for campo in campos:
                if not igual(a[chv].get(campo), g[chv].get(campo), tol):
                    ruins.append(f"{chv}.{campo}: API={a[chv].get(campo)!r} gold={g[chv].get(campo)!r}")
        return self.ver(grupo, pais, f"{descricao} ({len(g)} linhas comparadas): divergencias", 0, len(ruins), detalhe="; ".join(ruins[:4]))

    # -- grupos --------------------------------------------------------------------------------------------------
    def paises(self):
        api = self.get("/api/paises")
        g = self.gold("SELECT pais, nome_exibicao, iso2, fuso, tem_texto, usuarios, usuarios_elegiveis, conversas, primeira_data, ultima_data FROM gold.pais")
        self.linhas("paises", "", "Lista de paises x gold.pais", api, g, ("pais",), ("nome_exibicao", "iso2", "fuso", "tem_texto", "usuarios", "usuarios_elegiveis", "conversas", "primeira_data", "ultima_data"))

    def resumo(self, pais: str):
        a = self.get("/api/retencao/resumo", pais=pais)
        p = self.gold("SELECT * FROM gold.pais WHERE pais = %s", (pais,))[0]
        s = self.gold("SELECT sum(novos) novos, sum(elegiveis) el, sum(voltaram_7d) v FROM gold.agg_retorno_semana WHERE pais = %s", (pais,))[0]
        # as somas por semana (uma tabela) tem de dar o que gold.pais (outra tabela) diz: dois caminhos, mesmo numero
        self.ver("resumo", pais, "novos (API) = soma das semanas = gold.pais.usuarios", p["usuarios"], a["novos"])
        self.ver("resumo", pais, "soma das semanas (novos) = gold.pais.usuarios", p["usuarios"], s["novos"])
        self.ver("resumo", pais, "elegiveis (API) = gold.pais.usuarios_elegiveis", p["usuarios_elegiveis"], a["elegiveis"])
        self.ver("resumo", pais, "soma das semanas (elegiveis) = gold.pais.usuarios_elegiveis", p["usuarios_elegiveis"], s["el"])
        self.ver("resumo", pais, "voltaram em 7 dias (API) = gold.pais.voltaram_7d", p["voltaram_7d"], a["voltaram_7d"])
        self.ver("resumo", pais, "soma das semanas (voltaram) = gold.pais.voltaram_7d", p["voltaram_7d"], s["v"])
        self.ver("resumo", pais, "conversas (API) = gold.pais.conversas", p["conversas"], a["conversas"])
        taxa, lo, hi = taxa_ic(p["voltaram_7d"], p["usuarios_elegiveis"])
        for campo, esp in (("taxa", taxa), ("ic_lo", lo), ("ic_hi", hi)):
            self.ver("resumo", pais, f"retorno em 7 dias: {campo} recalculado em Python = API", esp, a[campo])
        v24 = a["voltou_24h"]
        self.ver("resumo", pais, "voltou em 24 h (API) = gold.pais.voltaram_24h", p["voltaram_24h"], v24["voltaram"])
        t24 = taxa_ic(p["voltaram_24h"], p["usuarios_elegiveis"])
        for campo, esp in zip(("taxa", "ic_lo", "ic_hi"), t24):
            self.ver("resumo", pais, f"voltou em 24 h: {campo} recalculado em Python = API", esp, v24[campo])
        r = self.gold("""SELECT sum(elegiveis) FILTER (WHERE nivel = 'Com recusa')::int com, sum(elegiveis)::int total
                         FROM gold.agg_retorno_fator WHERE pais = %s AND fator = 'recusa'""", (pais,))[0]
        total = r["total"]
        com = (r["com"] or 0) if total is not None else None
        self.ver("resumo", pais, "recusa: elegiveis com a medida (API) = gold.agg_retorno_fator", total, a["recusa_elegiveis"])
        for campo, esp in zip(("recusa_taxa", "recusa_ic_lo", "recusa_ic_hi"), taxa_ic(com, total)):
            self.ver("resumo", pais, f"recusa: {campo} recalculado em Python = API", esp, a[campo])

    def coortes(self, pais: str):
        api = self.get("/api/retencao/coortes", pais=pais)
        g = self.gold("SELECT semana, novos, elegiveis, voltaram_7d, taxa, ic_lo, ic_hi FROM gold.agg_retorno_semana WHERE pais = %s ORDER BY semana", (pais,))
        self.linhas("coortes", pais, "Semanas (API) x gold.agg_retorno_semana", api, g, ("semana",), ("novos", "elegiveis", "voltaram_7d", "taxa", "ic_lo", "ic_hi"))
        esperado = [taxa_ic(r["voltaram_7d"], r["elegiveis"]) for r in g]
        ruins = sum(1 for r, e in zip(g, esperado) if not (igual(r["taxa"], e[0]) and igual(r["ic_lo"], e[1], 1e-6) and igual(r["ic_hi"], e[2], 1e-6)))
        self.ver("coortes", pais, "taxa e margem de erro de cada semana recalculadas em Python = gold (divergencias)", 0, ruins)
        self.ver("coortes", pais, "amostra pequena na API = menos de 30 elegiveis", sum(1 for r in g if r["elegiveis"] < 30), sum(1 for r in api if r["amostra_pequena"]))

    def meses(self, pais: str):
        api = self.get("/api/retencao/meses", pais=pais)
        g = self.gold("""SELECT mes AS semana, sum(elegiveis)::int AS elegiveis, sum(voltaram_7d)::int AS voltaram_7d
                         FROM gold.agg_retorno_mes_fator WHERE pais = %s AND fator = 'modelo' GROUP BY mes""", (pais,))
        self.linhas("meses", pais, "Meses (API) x gold.agg_retorno_mes_fator", api, g, ("semana",), ("elegiveis", "voltaram_7d"))
        sem = self.gold("SELECT coalesce(sum(elegiveis), 0)::int e FROM gold.agg_retorno_semana WHERE pais = %s", (pais,))[0]["e"]
        self.ver("meses", pais, "soma dos meses (elegiveis) = soma das semanas (outra tabela da gold)", sem, sum(r["elegiveis"] for r in api))

    def fatores(self, pais: str):
        api = self.get("/api/retencao/fatores", pais=pais)
        g = self.gold("SELECT fator, nivel, elegiveis, voltaram_7d, taxa, ic_lo, ic_hi FROM gold.agg_retorno_fator WHERE pais = %s", (pais,))
        self.linhas("fatores", pais, "Fatores (API) x gold.agg_retorno_fator", api, g, ("fator", "nivel"), ("elegiveis", "voltaram_7d", "taxa", "ic_lo", "ic_hi"))
        so = self.get("/api/retencao/fatores", pais=pais, fator="modelo")
        self.ver("fatores", pais, "filtro fator=modelo devolve so o modelo", True, all(r["fator"] == "modelo" for r in so))
        el = self.gold("SELECT coalesce(sum(elegiveis), 0)::int e FROM gold.agg_retorno_fator WHERE pais = %s AND fator = 'modelo'", (pais,))[0]["e"]
        pe = self.gold("SELECT usuarios_elegiveis e FROM gold.pais WHERE pais = %s", (pais,))[0]["e"]
        self.ver("fatores", pais, "elegiveis somados por modelo = gold.pais.usuarios_elegiveis", pe, el)

    def comparacao(self):
        a = self.get("/api/retencao/comparacao")
        g = self.gold("""SELECT pais, sum(elegiveis)::int AS elegiveis, sum(voltaram_7d)::int AS voltaram_7d FROM gold.agg_retorno_semana
                         GROUP BY pais HAVING sum(elegiveis) >= 30""")
        for r in g:
            r["taxa"] = r["voltaram_7d"] / r["elegiveis"]
            r["ic_lo"], r["ic_hi"] = wilson(r["voltaram_7d"], r["elegiveis"])
        self.linhas("comparacao", "", "Paises (API) x soma das semanas, taxa e Wilson em Python", a["paises"], g, ("pais",), ("elegiveis", "voltaram_7d", "taxa", "ic_lo", "ic_hi"), tol=1e-6)
        tot_e, tot_v = sum(r["elegiveis"] for r in self.gold("SELECT elegiveis FROM gold.agg_retorno_semana")), sum(r["voltaram_7d"] for r in self.gold("SELECT voltaram_7d FROM gold.agg_retorno_semana"))
        self.ver("comparacao", "", "media geral: elegiveis (API) = soma de todas as semanas da gold", tot_e, a["geral"]["elegiveis"])
        self.ver("comparacao", "", "media geral: taxa (API) = voltaram / elegiveis de todos os paises", tot_v / tot_e, a["geral"]["taxa"])
        ge = self.gold("SELECT sum(usuarios_elegiveis)::int e, sum(voltaram_7d)::int v FROM gold.pais")[0]
        self.ver("comparacao", "", "media geral = soma de gold.pais (outra tabela)", (ge["e"], ge["v"]), (a["geral"]["elegiveis"], a["geral"]["voltaram_7d"]))
        ordem = [r["elegiveis"] for r in a["paises"]]
        self.ver("comparacao", "", "paises ordenados por elegiveis, do maior para o menor", ordem, sorted(ordem, reverse=True))

    def curva(self, pais: str):
        a = self.get("/api/retencao/curva", pais=pais)
        g = self.gold("SELECT dias::float AS dias, usuarios, voltaram FROM gold.agg_curva_retorno WHERE pais = %s", (pais,))
        for r in g:
            r["taxa"], r["ic_lo"], r["ic_hi"] = taxa_ic(r["voltaram"], r["usuarios"])
        self.linhas("curva", pais, "Pontos da curva (API) x gold.agg_curva_retorno", a["pontos"], g, ("dias",), ("usuarios", "voltaram", "taxa", "ic_lo", "ic_hi"), tol=1e-6)
        por = {r["dias"]: r for r in g}
        for nome, d in (("voltou_24h", 1.0), ("voltou_7d", 7.0), ("voltou_30d", 30.0)):
            esp = por.get(d)
            self.ver("curva", pais, f"destaque {nome} = ponto de {int(d)} dia(s) da gold", esp["voltaram"] if esp else None, (a[nome] or {}).get("voltaram"))
        s = self.gold("SELECT sum(elegiveis)::int AS el, sum(voltaram_7d)::int AS v FROM gold.agg_retorno_semana WHERE pais = %s", (pais,))[0]
        if por.get(7.0):
            self.ver("curva", pais, "ponto de 7 dias da curva = cartao do retorno em 7 dias (pessoas elegiveis e quem voltou)", (s["el"], s["v"]), (por[7.0]["usuarios"], por[7.0]["voltaram"]))
        taxas = [r["taxa"] for r in sorted(a["pontos"], key=lambda r: r["dias"]) if r["taxa"] is not None]
        self.ver("curva", pais, "a curva nunca decresce", True, all(x <= y + 1e-12 for x, y in zip(taxas, taxas[1:])))

    def estratos(self, pais: str):
        api = self.get("/api/retencao/estratos", pais=pais)
        g = self.gold("SELECT fator, familia, nivel, elegiveis, voltaram_7d FROM gold.agg_estrato WHERE pais = %s", (pais,))
        tratado = {"recusa": "Com recusa", "saudacao": "Saudação"}
        grupos = {}
        for r in g:
            grupos.setdefault((r["fator"], r["familia"]), {})[r["nivel"]] = r
        esperado, obtido = [], []
        for (fator, familia), niveis in grupos.items():
            t = niveis.get(tratado[fator])
            c = next((v for k, v in niveis.items() if k != tratado[fator]), None)
            dif = None
            if t and c and t["elegiveis"] >= 30 and c["elegiveis"] >= 30:
                pt, pc = t["voltaram_7d"] / t["elegiveis"], c["voltaram_7d"] / c["elegiveis"]
                ep = (pt * (1 - pt) / t["elegiveis"] + pc * (1 - pc) / c["elegiveis"]) ** 0.5
                dif = round((pt - pc) * 100, 6), round((pt - pc - 1.96 * ep) * 100, 6), round((pt - pc + 1.96 * ep) * 100, 6)
            esperado.append((fator, familia, dif))
        for r in api:
            d = r["diferenca"]
            obtido.append((r["fator"], r["familia"], None if d is None else (round(d["pp"], 6), round(d["ic_lo"], 6), round(d["ic_hi"], 6))))
        self.ver("estratos", pais, f"Diferenca simples de cada estrato ({len(esperado)}) recalculada em Python = API", sorted(esperado, key=str), sorted(obtido, key=str), tol=1e-6)

    def modelos(self, pais: str):
        a = self.get("/api/explorar/modelos", pais=pais)
        g = self.gold("SELECT modelo, conversas, conversas_texto, com_recusa, resp_media_chars, elegiveis, voltaram_7d FROM gold.agg_recusa_modelo WHERE pais = %s", (pais,))
        for r in g:
            r["retorno_taxa"], r["retorno_lo"], r["retorno_hi"] = taxa_ic(r["voltaram_7d"], r["elegiveis"])
            r["recusa_taxa"], r["recusa_lo"], r["recusa_hi"] = taxa_ic(r["com_recusa"], r["conversas_texto"])
        api = [{**v, "retorno_taxa": v["retorno"]["taxa"], "retorno_lo": v["retorno"]["ic_lo"], "retorno_hi": v["retorno"]["ic_hi"],
                "recusa_taxa": v["recusa"]["taxa"], "recusa_lo": v["recusa"]["ic_lo"], "recusa_hi": v["recusa"]["ic_hi"]} for v in a["versoes"]]
        self.linhas("modelos", pais, "Versoes do modelo (API) x gold.agg_recusa_modelo, taxas e Wilson em Python", api, g, ("modelo",),
                    ("conversas", "conversas_texto", "com_recusa", "resp_media_chars", "elegiveis", "voltaram_7d", "retorno_taxa", "retorno_lo", "retorno_hi",
                     "recusa_taxa", "recusa_lo", "recusa_hi"), tol=1e-6)
        for f in a["familias"]:
            fam = [r for r in g if (r["modelo"].startswith("gpt-4")) == (f["familia"] == "GPT-4")]
            self.ver("modelos", pais, f"{f['familia']}: elegiveis (agg_retorno_fator) = soma das versoes (agg_recusa_modelo)", sum(r["elegiveis"] for r in fam), f["elegiveis"])
            self.ver("modelos", pais, f"{f['familia']}: voltaram (agg_retorno_fator) = soma das versoes", sum(r["voltaram_7d"] for r in fam), f["voltaram_7d"])
        gm = self.gold("SELECT mes, conversas, conversas_gpt4 FROM gold.agg_modelo_mes WHERE pais = %s", (pais,))
        self.linhas("modelos", pais, "GPT-4 por mes (API) x gold.agg_modelo_mes", a["meses"], gm, ("mes",), ("conversas", "conversas_gpt4"))
        self.ver("modelos", pais, "soma das conversas por mes = soma das conversas por versao", sum(r["conversas"] for r in gm), sum(r["conversas"] for r in g))

    def concentracao(self, pais: str):
        a = self.get("/api/explorar/concentracao", pais=pais)
        p = self.gold("SELECT * FROM gold.pais WHERE pais = %s", (pais,))[0]
        fx = self.gold("SELECT faixa, usuarios, conversas FROM gold.agg_concentracao WHERE pais = %s", (pais,))
        grande = p["usuarios"] >= AMOSTRA_MINIMA
        self.ver("concentracao", pais, "pessoas somadas nas faixas = gold.pais.usuarios", p["usuarios"], sum(r["usuarios"] for r in fx))
        self.ver("concentracao", pais, "conversas somadas nas faixas = gold.pais.conversas", p["conversas"], sum(r["conversas"] for r in fx))
        self.ver("concentracao", pais, "top 10 (API) = gold.pais.top10_pct (escondido se < 30 pessoas)", p["top10_pct"] if grande else None, a["top10_pct"])
        if grande:
            self.linhas("concentracao", pais, "Faixas (API) x gold.agg_concentracao", a["faixas"], fx, ("faixa",), ("usuarios", "conversas"))
            self.ver("concentracao", pais, "percentuais das pessoas somam 100%", 1.0, sum(f["pct_pessoas"] for f in a["faixas"]), tol=1e-9)
            t_sem = taxa_ic(p["voltaram_sem_top10"], p["elegiveis_sem_top10"])
            self.ver("concentracao", pais, "retorno sem as 10 mais ativas: taxa recalculada = API", t_sem[0], a["retorno_sem_top10"]["taxa"])

    def uso_hora(self, pais: str):
        a = self.get("/api/explorar/uso-hora", pais=pais)
        g = self.gold("SELECT dia_semana, hora, conversas FROM gold.agg_uso_hora WHERE pais = %s", (pais,))
        self.linhas("uso_hora", pais, "Celulas dia x hora (API) x gold.agg_uso_hora", a["celulas"], g, ("dia_semana", "hora"), ("conversas",))
        total = sum(r["conversas"] for r in g)
        self.ver("uso_hora", pais, "total de conversas = gold.pais.conversas", self.gold("SELECT conversas c FROM gold.pais WHERE pais = %s", (pais,))[0]["c"], total)
        exp = sum(r["conversas"] for r in g if r["dia_semana"] <= 5 and 9 <= r["hora"] < 18)
        self.ver("uso_hora", pais, "% no expediente recalculada = API", exp / total if total else None, a["pct_expediente"])

    def uso_diario(self, pais: str):
        a = self.get("/api/uso/diario", pais=pais)
        g = self.gold("SELECT dia, conversas, usuarios_ativos FROM gold.agg_uso_dia WHERE pais = %s", (pais,))
        self.linhas("uso_diario", pais, "Dias (API) x gold.agg_uso_dia", a, g, ("dia",), ("conversas", "usuarios_ativos"))

    def efeitos(self, pais: str):
        a = self.get("/api/efeitos", pais=pais)
        g = self.gold("SELECT fator, contraste, n, n_tratados, n_controle, efeito_bruto_pp, efeito_pp, ic_lo, ic_hi, e_value FROM gold.efeito_fator WHERE pais = %s", (pais,))
        self.linhas("efeitos", pais, "Efeitos (API) x gold.efeito_fator", a, g, ("fator", "contraste"), ("n", "n_tratados", "n_controle", "efeito_bruto_pp", "efeito_pp", "ic_lo", "ic_hi", "e_value"))
        det = [(r["ic_lo"] > 0 or r["ic_hi"] < 0) for r in a]
        self.ver("efeitos", pais, "ordem: detectaveis primeiro", det, sorted(det, reverse=True))
        self.ver("efeitos", pais, "nenhum efeito com grupo menor que 30", 0, sum(1 for r in a if r["n_tratados"] < 30 or r["n_controle"] < 30))

    def decomposicao(self, pais: str):
        for fator in ("modelo", "turnos_da_primeira_conversa", "periodo_do_dia", "tema"):
            a = self.get("/api/retencao/decomposicao", pais=pais, fator=fator)
            if not a["disponivel"]:
                continue
            g = self.gold("""SELECT mes::text, sum(elegiveis)::int e, sum(voltaram_7d)::int v FROM gold.agg_retorno_mes_fator
                             WHERE pais = %s AND fator = %s AND mes::text = ANY(%s) GROUP BY mes""", (pais, fator, [a["de"], a["para"]]))
            por = {r["mes"]: r["v"] / r["e"] for r in g}
            self.ver("decomposicao", pais, f"{fator}: taxa do mes de partida (API) = gold", por.get(a["de"]), a["taxa_de"])
            self.ver("decomposicao", pais, f"{fator}: taxa do mes de chegada (API) = gold", por.get(a["para"]), a["taxa_para"])
            c = a["componentes_pp"]
            self.ver("decomposicao", pais, f"{fator}: mix + taxa + interacao = variacao total", a["delta_pp"], c["mix"] + c["taxa"] + c["interacao"], tol=1e-9)
            self.ver("decomposicao", pais, f"{fator}: variacao total = diferenca das taxas da gold", (por[a["para"]] - por[a["de"]]) * 100, a["delta_pp"], tol=1e-6)

    def catalogo_e_qualidade(self):
        a = self.get("/api/catalogo")
        g = self.gold("SELECT indicador_id, nome, pergunta, unidade, denominador, formula, fonte, periodo_para_nada FROM (SELECT *, 1 AS periodo_para_nada FROM gold.catalogo_indicador) x")
        self.linhas("catalogo", "", "Catalogo de indicadores (API) x gold.catalogo_indicador", a, g, ("indicador_id",), ("nome", "pergunta", "unidade", "denominador", "formula", "fonte"))
        q = self.get("/api/qualidade")
        ex = self.gold("SELECT id, status FROM ops.etl_execucao ORDER BY id DESC LIMIT 1")[0]
        self.ver("qualidade", "", "execucao mostrada = ultima execucao do ETL", ex["id"], q["execucao"]["id"])
        qa = self.gold("SELECT count(*) n, count(*) FILTER (WHERE passou) ok FROM ops.qa_resultado WHERE execucao_id = %s", (ex["id"],))[0]
        self.ver("qualidade", "", "conferencias mostradas = ops.qa_resultado da execucao", (qa["n"], qa["ok"]), (len(q["verificacoes"]), sum(1 for v in q["verificacoes"] if v["passou"])))
        pq = self.gold("SELECT codigo, afetadas, total FROM gold.problema_qualidade")
        self.linhas("qualidade", "", "Problemas de qualidade (API) x gold.problema_qualidade", q["problemas"], pq, ("codigo",), ("afetadas", "total"))
        s = self.get("/api/saude")
        self.ver("qualidade", "", "/saude: ultima execucao = ultima execucao do ETL", ex["id"], s["ultima_execucao_etl"]["id"])

    def seguranca(self, client_sem_cookie):
        rotas = ["/api/paises", "/api/retencao/resumo", "/api/retencao/coortes", "/api/efeitos", "/api/explorar/modelos", "/api/qualidade", "/api/catalogo"]
        sem = [r for r in rotas if client_sem_cookie.get(r).status_code != 401]
        self.ver("seguranca", "", "rotas protegidas sem sessao devolvem 401 (as que nao devolveram)", [], sem)
        ruim = client_sem_cookie.get("/api/paises", cookies={"sessao": "token-invalido"}).status_code
        self.ver("seguranca", "", "token invalido devolve 401", 401, ruim)
        self.ver("seguranca", "", "pais inexistente devolve 404", 404, self.c.get("/api/retencao/resumo", params={"pais": "Atlantida"}).status_code)

    def todos(self, paises: list[str], client_sem_cookie=None):
        self.paises(); self.comparacao(); self.catalogo_e_qualidade()
        for p in paises:
            for f in (self.resumo, self.coortes, self.meses, self.fatores, self.curva, self.estratos, self.modelos, self.concentracao, self.uso_hora, self.uso_diario, self.efeitos, self.decomposicao):
                f(p)
        if client_sem_cookie is not None:
            self.seguranca(client_sem_cookie)
        return self.checks


def camadas(db) -> list[Check]:
    """Conciliacao entre as camadas, direto no banco (usuario do ETL, que enxerga bronze, silver e gold)."""
    def um(sql):
        return list(db.execute(sql).fetchone().values())[0]
    ult = "(SELECT max(id) FROM ops.etl_execucao)"
    cs: list[Check] = []

    def ver(descricao, esperado, obtido):
        cs.append(Check("camadas", "", descricao, esperado, obtido, igual(esperado, obtido)))

    lote = um(f"SELECT sum(linhas) FROM ops.bronze_lote WHERE execucao_id = {ult}")
    ver("Bronze: linhas de bronze.wildchat = soma das linhas dos arquivos da semente (ops.bronze_lote)", lote, um("SELECT count(*) FROM bronze.wildchat"))
    ver("Bronze: linhas do arquivo do Brasil = linhas com country = Brazil", um(f"SELECT linhas FROM ops.bronze_lote WHERE execucao_id = {ult} AND arquivo = 'wildchat_brasil.parquet'"),
        um("SELECT count(*) FROM bronze.wildchat WHERE country = 'Brazil'"))
    excl = um(f"SELECT count(*) FROM auditoria.registro_excluido WHERE execucao_id = {ult}")
    ver("Bronze -> Silver: bronze = silver + excluidas", um("SELECT count(*) FROM bronze.wildchat"), um("SELECT count(*) FROM silver.fato_conversa") + excl)
    ver("Silver: soma das conversas por pessoa = conversas", um("SELECT count(*) FROM silver.fato_conversa"), um("SELECT sum(convs_total) FROM silver.fato_usuario"))
    ver("Silver -> Gold: pessoas (gold.pais) = pessoas da silver", um("SELECT count(*) FROM silver.fato_usuario"), um("SELECT sum(usuarios) FROM gold.pais"))
    ver("Silver -> Gold: conversas (gold.pais) = conversas da silver", um("SELECT count(*) FROM silver.fato_conversa"), um("SELECT sum(conversas) FROM gold.pais"))
    ver("Silver -> Gold: elegiveis somados por semana = elegiveis da silver", um("SELECT count(*) FROM silver.fato_usuario WHERE elegivel"), um("SELECT sum(elegiveis) FROM gold.agg_retorno_semana"))
    ver("Silver -> Gold: voltaram somados por semana = voltaram da silver", um("SELECT count(*) FROM silver.fato_usuario WHERE elegivel AND voltou_7d"), um("SELECT sum(voltaram_7d) FROM gold.agg_retorno_semana"))
    ver("Silver -> Gold: conversas por dia (uso diario) = conversas da silver", um("SELECT count(*) FROM silver.fato_conversa"), um("SELECT sum(conversas) FROM gold.agg_uso_dia"))
    ver("Silver -> Gold: conversas por hora = conversas da silver", um("SELECT count(*) FROM silver.fato_conversa"), um("SELECT sum(conversas) FROM gold.agg_uso_hora"))
    ver("Silver -> Gold: conversas por mes e modelo = conversas da silver", um("SELECT count(*) FROM silver.fato_conversa"), um("SELECT sum(conversas) FROM gold.agg_modelo_mes"))
    ver("Silver -> Gold: pessoas na curva (30 dias) = pessoas com janela de 30 dias", um("SELECT count(*) FROM silver.fato_usuario WHERE janela_30d"), um("SELECT sum(usuarios) FROM gold.agg_curva_retorno WHERE dias = 30"))
    ver("Silver -> Gold: elegiveis por modelo = elegiveis da silver", um("SELECT count(*) FROM silver.fato_usuario WHERE elegivel"), um("SELECT sum(elegiveis) FROM gold.agg_retorno_fator WHERE fator = 'modelo'"))
    ver("Silver -> Gold: elegiveis por versao do modelo = elegiveis da silver", um("SELECT count(*) FROM silver.fato_usuario WHERE elegivel"), um("SELECT sum(elegiveis) FROM gold.agg_recusa_modelo"))
    return cs
