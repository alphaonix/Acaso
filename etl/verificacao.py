"""VERIFICACAO DE INTEGRIDADE: o que esta no banco AGORA e exatamente o que a ultima carga publicada deixou?

Por que existe: o ETL confere as camadas no momento em que as constroi. Se alguem alterar a silver ou a gold DEPOIS (um UPDATE solto, uma
carga "por fora"), as conferencias da carga nao veem isso. Aqui o estado vivo das tres camadas e medido de novo e comparado, medida
por medida (contagens, vazios e "impressoes digitais" de todas as linhas), com o que foi gravado em auditoria.metrica quando a carga terminou.
Qualquer diferenca = alguem mexeu fora do ETL. Tambem confere que a trava de escrita (migracao 025) continua ligada em todas as tabelas.

Quando roda:
  * automaticamente, no INICIO de toda carga, antes de reconstruir (a carga reconstroi tudo e "cura" a alteracao, mas o alerta fica registrado);
  * quando voce quiser:  docker compose --profile operacao run --rm verificar-integridade   (sai com erro se houver divergencia).
Cada verificacao fica em auditoria.verificacao.
"""
import json
import math
import sys

from camadas import bronze, gold, silver
from comum import banco
from comum.qualidade import Resultado

MAX_DETALHE = 15


def ultima_carga_publicada(ops, antes_de: int | None = None) -> int | None:
    """Ultima carga que terminou bem (ok ou alerta) e tem medidas gravadas, opcionalmente anterior a `antes_de`."""
    r = ops.execute("""SELECT max(e.id) FROM ops.etl_execucao e WHERE e.status IN ('ok', 'alerta') AND (%s::bigint IS NULL OR e.id < %s)
                         AND EXISTS (SELECT 1 FROM auditoria.metrica m WHERE m.execucao_id = e.id)""", (antes_de, antes_de)).fetchone()
    return r[0] if r else None


def _gravadas(ops, carga: int) -> dict:
    linhas = ops.execute("SELECT camada, metrica, escopo, valor, texto FROM auditoria.metrica WHERE execucao_id = %s", (carga,)).fetchall()
    return {(c, m, e): (None if v is None else float(v), t) for c, m, e, v, t in linhas}


def _agora(dw) -> dict:
    medidas = bronze.diagnosticar_bronze(dw) + silver.diagnosticar_silver(dw) + gold.diagnosticar_gold(dw)
    return {(m.camada, m.nome, m.escopo): (m.valor, m.texto) for m in medidas}


def _igual(a, b) -> bool:
    (va, ta), (vb, tb) = a, b
    if ta != tb:
        return False
    if va is None or vb is None:
        return va is None and vb is None
    return math.isclose(va, vb, rel_tol=1e-9, abs_tol=1e-9)       # o historico guarda numeric (15 digitos); o vivo e float


def diferencas(ops, dw, carga: int) -> tuple[list[str], int]:
    """(descricao das diferencas, quantas medidas foram comparadas) entre o estado vivo e o gravado pela carga."""
    gravadas, agora = _gravadas(ops, carga), _agora(dw)
    difs = []
    for chave in sorted(gravadas.keys() | agora.keys()):
        nome = f"{chave[0]} | {chave[1]}{'[' + chave[2] + ']' if chave[2] else ''}"
        if chave not in agora:
            difs.append(f"{nome}: existia na carga {carga} e sumiu")
        elif chave not in gravadas:
            if not any(c[:2] == chave[:2] for c in gravadas):
                continue          # medida criada por uma versao nova do codigo (a carga anterior nem media isso): nao e alteracao por fora
            difs.append(f"{nome}: apareceu depois da carga {carga}")
        elif not _igual(gravadas[chave], agora[chave]):
            difs.append(f"{nome}: carga {carga} deixou {gravadas[chave][1] or gravadas[chave][0]}, agora esta {agora[chave][1] or agora[chave][0]}")
    return difs, len(gravadas)


def trava_desligada(ops) -> list[str]:
    return [f"{c}.{t}" for c, t in ops.execute("SELECT camada, tabela FROM auditoria.protecao_camadas WHERE NOT protegida ORDER BY 1, 2").fetchall()]


def estado_publicado(ops, dw, exec_id: int | None = None, origem: str = "antes_da_carga") -> list[Resultado]:
    """Conferencias de integridade do que esta publicado; grava o resumo em auditoria.verificacao."""
    carga = ultima_carga_publicada(ops, exec_id)
    if carga is None:
        return [Resultado("integridade", "Integridade: ainda nao ha carga publicada para comparar", "sem carga anterior", "sem carga anterior", True)]
    difs, comparadas = diferencas(ops, dw, carga)
    sem_trava = trava_desligada(ops)
    ops.execute("INSERT INTO auditoria.verificacao (origem, carga_verificada, conferencias, divergencias, detalhe) VALUES (%s, %s, %s, %s, %s)",
                (origem, carga, comparadas, len(difs) + len(sem_trava), json.dumps((difs + [f"trava desligada em {t}" for t in sem_trava])[:MAX_DETALHE])))
    for d in difs[:MAX_DETALHE]:
        print(f"[integridade] ALTERADO FORA DO ETL: {d}", flush=True)
    return [
        Resultado("integridade", f"Integridade: bronze, silver e gold continuam exatamente como a carga {carga} as deixou ({comparadas} medidas, "
                                 "inclusive a impressao digital de todas as linhas): ninguem alterou fora do ETL", "0", str(len(difs)), not difs),
        Resultado("integridade", "Integridade: a trava de escrita esta ligada em todas as tabelas das camadas", "0", str(len(sem_trava)), not sem_trava),
    ]


def main() -> int:
    """Verificacao sob demanda: integridade do publicado + as conferencias de conservacao entre camadas, rodadas de novo no banco vivo."""
    ops, dw = banco.conectar(autocommit=True), banco.conectar(autocommit=True)
    carga = ultima_carga_publicada(ops)
    if carga is None:
        print("Nenhuma carga publicada ainda: nada a verificar.")
        return 0
    resultados = estado_publicado(ops, dw, None, "manual")
    for nome, validar in (("bronze", bronze.validar_bronze), ("silver", silver.validar_silver), ("gold", gold.validar_gold)):
        resultados += validar(dw, carga)
    falhas = [r for r in resultados if not r.passou]
    for r in resultados:
        print(f"[{'OK ' if r.passou else 'FALHOU'}] [{r.transicao}] {r.verificacao}: esperado {r.esperado}, obtido {r.obtido}")
    print(f"\nCarga verificada: {carga}. {len(resultados) - len(falhas)} de {len(resultados)} conferencias batem.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
