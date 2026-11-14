"""SILVER: executa os passos do silver/sql.py na ordem certa (bronze -> silver). Roda DENTRO da transacao de carga.

Ordem:  limpar -> bruto (achatar a bronze) -> conv0 (limpar) -> dimensoes (pais e tema) -> conv (derivar por conversa)
        -> usuarios (visitas, retorno, elegibilidade) -> gravar silver.fato_conversa e silver.fato_usuario.
As tabelas temporarias (bruto, conv0, conv, usuarios) ficam vivas ate o fim da transacao: a auditoria usa `bruto` e `conv0`.
Regras de negocio (30 min, 7 dias, 30 dias, palavras de tema e recusa): comum/definicoes.py.
"""
from comum.definicoes import PAIS_COM_TEXTO, PAIS_ISO, IDIOMA_PADRAO, TEMAS, meta_pais

from .limpar import limpar_silver
from .sql import SQL_BRUTO, SQL_CONV, SQL_CONV0, SQL_INSERE_CONVERSA, SQL_INSERE_USUARIO, SQL_USUARIOS


def construir_silver(dw) -> dict:
    """Dentro da transacao `dw` (silver ja esvaziada e bronze ja carregada). Devolve estatisticas de qualidade."""
    limpar_silver(dw)
    with dw.cursor() as cur:
        cur.execute("SET LOCAL work_mem = '256MB'")   # ordenacoes/janelas sobre ~840 mil linhas
        cur.execute(SQL_BRUTO)
        lidas, sem_inicio, sem_ip, pais_nulo = cur.execute(
            """SELECT count(*), count(*) FILTER (WHERE start_ts IS NULL), count(*) FILTER (WHERE hashed_ip IS NULL),
                      count(*) FILTER (WHERE pais = 'Desconhecido') FROM bruto""").fetchone()
        cur.execute(SQL_CONV0)
        carregadas = cur.execute("SELECT count(*) FROM conv0").fetchone()[0]
        aptas = cur.execute("SELECT count(*) FROM bruto WHERE start_ts IS NOT NULL AND hashed_ip IS NOT NULL").fetchone()[0]

        # dimensoes: tema e pais (fuso por pais; ver PAISES_META e a premissa de fuso unico)
        cur.executemany("INSERT INTO silver.dim_tema (tema_id, tema) VALUES (%s, %s)", TEMAS)
        dim_pais = []
        for (p,) in cur.execute("SELECT DISTINCT pais FROM conv0 ORDER BY pais").fetchall():
            nome, fuso, aprox = meta_pais(p)
            dim_pais.append((p, nome, fuso, aprox, IDIOMA_PADRAO.get(p, "en"), p == PAIS_COM_TEXTO, PAIS_ISO.get(p)))
        cur.executemany("""INSERT INTO silver.dim_pais (pais, nome_exibicao, fuso, fuso_aproximado, idioma_padrao, tem_texto, iso2)\n                           VALUES (%s, %s, %s, %s, %s, %s, %s)""", dim_pais)

        cur.execute(SQL_CONV)
        cur.execute(SQL_USUARIOS)
        cur.execute(SQL_INSERE_CONVERSA)
        cur.execute(SQL_INSERE_USUARIO)
    return dict(lidas=lidas, sem_inicio=sem_inicio, sem_ip=sem_ip, pais_nulo=pais_nulo,
                duplicadas=aptas - carregadas, carregadas=carregadas)
