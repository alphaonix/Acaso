"""Detector de DERIVA: compara as medidas desta carga com as da carga anterior bem-sucedida e diz o que mudou.

Regra (PDF 4.1: "a definicao de um indicador nao pode mudar sem ninguem perceber"):
  * MESMA semente (mesmos arquivos, mesmo sha256): os numeros tem de ser IGUAIS. Qualquer diferenca quer dizer que uma regra, um
    parametro ou o proprio codigo mudou (ou que o resultado nao e reprodutivel): a conferencia fica vermelha e as diferencas vao para o log.
  * Semente DIFERENTE: contagens mudam por natureza; so se aponta variacao acima da tolerancia (20%).
Por padrao a deriva gera ALERTA (a carga e publicada e o status fica 'alerta'); com DERIVA_ESTRITA=1 ela derruba a carga.
Na carga seguinte, a comparacao parte da carga que gerou o alerta: o alerta aparece uma vez por mudanca.
"""
from .qualidade import Resultado

TOLERANCIA = 0.20      # semente diferente: variacao relativa acima disso e apontada
MAX_NO_LOG = 12        # quantas diferencas mostrar no log (todas ficam em auditoria.mudancas_entre_cargas)


def semente_id(ops, execucao_id: int) -> str | None:
    """Impressao digital da semente: o que foi lido nesta carga (sha256 dos arquivos, em ordem)."""
    r = ops.execute("SELECT md5(string_agg(sha256, '|' ORDER BY arquivo)) FROM ops.bronze_lote WHERE execucao_id = %s", (execucao_id,)).fetchone()
    return r[0] if r else None


def carga_anterior(ops, execucao_id: int) -> int | None:
    """Ultima carga anterior bem-sucedida (status ok ou alerta) que tenha metricas gravadas."""
    r = ops.execute("""SELECT max(e.id) FROM ops.etl_execucao e
                       WHERE e.id < %s AND e.status IN ('ok', 'alerta')
                         AND EXISTS (SELECT 1 FROM auditoria.metrica m WHERE m.execucao_id = e.id)""", (execucao_id,)).fetchone()
    return r[0] if r else None


def diferencas(ops, execucao_id: int, anterior: int, camada: str) -> list[tuple]:
    """(metrica, escopo, antes, depois) das medidas presentes nas duas cargas cujo valor ou texto mudou."""
    return ops.execute("""
        SELECT n.metrica, n.escopo, coalesce(v.valor::text, v.texto), coalesce(n.valor::text, n.texto), v.valor, n.valor
        FROM auditoria.metrica n JOIN auditoria.metrica v USING (camada, metrica, escopo)
        WHERE n.execucao_id = %s AND v.execucao_id = %s AND n.camada = %s
          AND (n.valor IS DISTINCT FROM v.valor OR n.texto IS DISTINCT FROM v.texto)
        ORDER BY n.metrica, n.escopo""", (execucao_id, anterior, camada)).fetchall()


def comparar(ops, execucao_id: int, camada: str) -> tuple[Resultado, list[str]]:
    """Devolve o resultado da conferencia de deriva da camada e as linhas de log com as diferencas."""
    anterior = carga_anterior(ops, execucao_id)
    nome = f"Deriva ({camada}): sem mudar a semente, os numeros da camada nao mudam em relacao a carga anterior"
    if anterior is None:
        return Resultado("deriva", nome, "sem carga anterior", "sem carga anterior", True), []
    mesma = semente_id(ops, execucao_id) == semente_id(ops, anterior)
    difs = diferencas(ops, execucao_id, anterior, camada)
    if not mesma:
        # semente nova: so conta variacao grande em medidas numericas
        difs = [d for d in difs if d[4] is not None and d[4] != 0 and abs(d[5] - d[4]) / abs(d[4]) > TOLERANCIA]
        nome = f"Deriva ({camada}): com semente nova, nenhuma medida varia mais de {int(TOLERANCIA * 100)}% em relacao a carga anterior"
    linhas = [f"[deriva] {camada} | {m}{'[' + e + ']' if e else ''}: {a} -> {d}" for m, e, a, d, _, _ in difs[:MAX_NO_LOG]]
    if len(difs) > MAX_NO_LOG:
        linhas.append(f"[deriva] {camada} | ... e mais {len(difs) - MAX_NO_LOG} (consulte auditoria.mudancas_entre_cargas)")
    return Resultado("deriva", f"{nome} (carga anterior: {anterior})", "0", str(len(difs)), len(difs) == 0), linhas
