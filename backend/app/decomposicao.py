"""Decomposicao shift-share do retorno entre dois periodos (mix x taxa x interacao). Funcao pura, sem banco: testada em tests/.

  R = soma_k w_k r_k   (w = peso do nivel k entre os elegiveis do periodo; r = taxa de retorno do nivel)
  mix       = soma (w1 - w0) r0     -> mudou QUEM chegou
  taxa      = soma w0 (r1 - r0)     -> mudou o retorno DENTRO de cada perfil
  interacao = soma (w1 - w0)(r1 - r0)
As tres somam exatamente R1 - R0. Nivel ausente num periodo tem peso zero e usa a taxa geral do periodo (nao altera a soma).
"""

Periodo = dict[str, tuple[int, int]]   # nivel -> (elegiveis, voltaram_7d)


def decompor(por_mes: dict[str, Periodo], de: str, para: str) -> dict:
    n0 = sum(n for n, _ in por_mes[de].values()); v0 = sum(v for _, v in por_mes[de].values())
    n1 = sum(n for n, _ in por_mes[para].values()); v1 = sum(v for _, v in por_mes[para].values())
    r0g, r1g = v0 / n0, v1 / n1
    niveis, mix, taxa, inter = [], 0.0, 0.0, 0.0
    for k in sorted(set(por_mes[de]) | set(por_mes[para])):
        a, b = por_mes[de].get(k, (0, 0)), por_mes[para].get(k, (0, 0))
        w0, w1 = a[0] / n0, b[0] / n1
        r0 = a[1] / a[0] if a[0] else r0g
        r1 = b[1] / b[0] if b[0] else r1g
        mix += (w1 - w0) * r0; taxa += w0 * (r1 - r0); inter += (w1 - w0) * (r1 - r0)
        niveis.append({"nivel": k, "peso_de": w0, "peso_para": w1, "taxa_de": r0 if a[0] else None, "taxa_para": r1 if b[0] else None,
                       "n_de": a[0], "n_para": b[0], "contrib_mix": (w1 - w0) * r0})
    delta = r1g - r0g
    return {"n_de": n0, "n_para": n1, "taxa_de": r0g, "taxa_para": r1g, "delta_pp": delta * 100,
            "componentes_pp": {"mix": mix * 100, "taxa": taxa * 100, "interacao": inter * 100},
            "soma_confere": abs((mix + taxa + inter) - delta) < 1e-9, "niveis": niveis}