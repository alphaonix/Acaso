"""Auditoria e linhagem da SILVER (schema `auditoria`, ADR-005). Roda DENTRO da transacao de carga, logo depois de construir a silver, e
registra: quantas conversas ha em cada camada (view auditoria.camadas), o que foi excluido da bronze para a silver (linha a linha), os valores vazios
(nulos) antes e depois, exemplos de antes e depois de cada tratamento, e o funil por pais.
Nao grava texto de conversa nem IP: so contagens, nomes de coluna e identificadores tecnicos (bronze_id, hash da conversa).
Usa as tabelas temporarias `bruto` e `conv0` criadas pela silver (ainda vivas na mesma transacao).
As colunas do funil que vem da gold (gold_usuarios, gold_conversas) sao completadas depois, em camadas/gold/auditoria.py.
"""

# (codigo, coluna na bronze, coluna na silver, SQL bronze -> (linhas, nulos), SQL silver -> (linhas, nulos) ou None, acao, tratamento)
_B = "SELECT count(*), count(*) FILTER (WHERE {c} IS NULL) FROM bronze.wildchat"
_S = "SELECT count(*), count(*) FILTER (WHERE {c} IS NULL) FROM silver.fato_conversa"
NULOS = [
    ("pais", "country", "pais", _B.format(c="country"), _S.format(c="pais"), "preenchido",
     "Pais nulo vira 'Desconhecido'; a linha e mantida"),
    ("estado", "state", "estado", _B.format(c="state"), _S.format(c="estado"), "mantido",
     "Estado ausente permanece nulo (a tela agrupa como 'sem estado')"),
    ("idioma", "language", "idioma", _B.format(c="language"), _S.format(c="idioma"), "mantido", "Copiado como veio"),
    ("modelo", "model", "modelo", _B.format(c="model"), _S.format(c="modelo"), "mantido", "Copiado como veio"),
    ("turnos", "turn", "turnos", _B.format(c="turn"), _S.format(c="turnos"), "mantido", "Copiado como veio"),
    ("ip", "hashed_ip", "usuario_id", _B.format(c="hashed_ip"), _S.format(c="usuario_id"), "excluido",
     "Sem IP nao ha como identificar o usuario: a linha e excluida"),
    ("inicio", "primeira_resposta_ts", "inicio_utc",
     "SELECT count(*), count(*) FILTER (WHERE primeira_resposta_ts IS NULL) FROM bronze.wildchat",
     _S.format(c="inicio_utc"), "excluido", "O inicio e o horario da 1a resposta do assistente (primeira_resposta_ts), igual para todos os paises. Sem horario a linha seria excluida"),
    ("fim", "timestamp", "fim_utc", _B.format(c='"timestamp"'), _S.format(c="fim_utc"), "mantido", "Copiado como veio (UTC)"),
    ("msg_usuario_horario", "conversation[1].timestamp", "(nao usado)",
     "SELECT count(*) FILTER (WHERE conversation IS NOT NULL), count(*) FILTER (WHERE conversation IS NOT NULL AND conversation->0->>'timestamp' IS NULL) FROM bronze.wildchat",
     None, "ignorado",
     "A 1a mensagem (do usuario) nao tem horario no WildChat (vazia em todas as conversas com texto): por isso o inicio vem da 2a mensagem, a 1a resposta do assistente"),
    ("texto", "conversation (texto)", "tema_id, recusa, tamanhos",
     _B.format(c="conversation"), _S.format(c="tema_id"), "derivado",
     "Fora do Brasil nao ha texto: tema e recusa ficam nulos por desenho. No Brasil o texto vira variaveis e e descartado"),
    ("redigida", "redacted", "redigida", _B.format(c="redacted"), _S.format(c="redigida"), "mantido", "Copiado como veio"),
]

# Linhas da bronze que NAO chegaram a silver, com o motivo. `bruto` = bronze achatada; `conv0` = o que sobrou da limpeza.
SQL_EXCLUIDOS = """
INSERT INTO auditoria.registro_excluido (execucao_id, bronze_id, conversation_hash, pais, motivo, mantida_bronze_id)
SELECT %(e)s, b.bronze_id, b.conversation_hash, b.pais,
       CASE WHEN b.start_ts IS NULL THEN 'sem_inicio' WHEN b.hashed_ip IS NULL THEN 'sem_ip' ELSE 'duplicata_exata' END,
       k.bronze_id
FROM bruto b
LEFT JOIN conv0 k ON k.conversation_hash = b.conversation_hash AND k.hashed_ip = b.hashed_ip AND k.start_ts = b.start_ts
WHERE NOT EXISTS (SELECT 1 FROM conv0 c WHERE c.bronze_id = b.bronze_id)
"""

# O funil por pais; a linha '(todos)' e a soma.
SQL_FLUXO = """
INSERT INTO auditoria.fluxo_pais (execucao_id, pais, bronze_linhas, excl_sem_inicio, excl_sem_ip, excl_duplicadas,
                                  silver_conversas, silver_usuarios, gold_usuarios, gold_conversas, pais_tratado)
WITH b AS (SELECT coalesce(country, 'Desconhecido') AS pais, count(*) AS linhas, count(*) FILTER (WHERE country IS NULL) AS tratado
           FROM bronze.wildchat GROUP BY 1),
x AS (SELECT pais, count(*) FILTER (WHERE motivo = 'sem_inicio') AS sem_inicio, count(*) FILTER (WHERE motivo = 'sem_ip') AS sem_ip,
             count(*) FILTER (WHERE motivo = 'duplicata_exata') AS dup
      FROM auditoria.registro_excluido WHERE execucao_id = %(e)s GROUP BY pais),
sc AS (SELECT pais, count(*) AS n FROM silver.fato_conversa GROUP BY pais),
su AS (SELECT pais, count(*) AS n FROM silver.fato_usuario GROUP BY pais)
SELECT %(e)s, b.pais, b.linhas, coalesce(x.sem_inicio, 0), coalesce(x.sem_ip, 0), coalesce(x.dup, 0),
       coalesce(sc.n, 0), coalesce(su.n, 0), coalesce(g.usuarios, 0), coalesce(g.conversas, 0), b.tratado
FROM b LEFT JOIN x USING (pais) LEFT JOIN sc USING (pais) LEFT JOIN su USING (pais) LEFT JOIN gold.pais g USING (pais)
"""
SQL_FLUXO_TOTAL = """
INSERT INTO auditoria.fluxo_pais
SELECT execucao_id, '(todos)', sum(bronze_linhas), sum(excl_sem_inicio), sum(excl_sem_ip), sum(excl_duplicadas),
       sum(silver_conversas), sum(silver_usuarios), sum(gold_usuarios), sum(gold_conversas), sum(pais_tratado)
FROM auditoria.fluxo_pais WHERE execucao_id = %(e)s GROUP BY execucao_id
"""

# Exemplos reais do Brasil (5 por tratamento, escolhidos por hash para variar). Formato campo=valor, sem texto e sem IP.
_UTC = "'YYYY-MM-DD HH24:MI:SS'"
SQLS_ANTES_DEPOIS = [
    """INSERT INTO auditoria.antes_depois (execucao_id, tratamento, ordem, bronze_id, pais, antes, depois)
       SELECT %(e)s, 'pais_nulo', (row_number() OVER (ORDER BY bronze_id))::smallint, bronze_id, 'Desconhecido',
              'country=NULL', 'pais=Desconhecido'
       FROM (SELECT bronze_id FROM bronze.wildchat WHERE country IS NULL ORDER BY md5(bronze_id::text) LIMIT 5) x""",
    f"""INSERT INTO auditoria.antes_depois (execucao_id, tratamento, ordem, bronze_id, pais, antes, depois)
       SELECT %(e)s, 'inicio_conversa', (row_number() OVER (ORDER BY f.bronze_id))::smallint, f.bronze_id, f.pais,
              'timestamp(ultimo turno)=' || to_char(b."timestamp" AT TIME ZONE 'UTC', {_UTC}) || '; mensagem_do_usuario.timestamp=NULL',
              'inicio_utc=' || to_char(f.inicio_utc AT TIME ZONE 'UTC', {_UTC}) || '; origem=1a resposta do assistente'
       FROM (SELECT bronze_id, pais, inicio_utc FROM silver.fato_conversa WHERE pais = 'Brazil'
             ORDER BY md5(bronze_id::text) LIMIT 5) f
       JOIN bronze.wildchat b USING (bronze_id)""",
    f"""INSERT INTO auditoria.antes_depois (execucao_id, tratamento, ordem, bronze_id, pais, antes, depois)
       SELECT %(e)s, 'fuso_local', (row_number() OVER (ORDER BY u.usuario_id))::smallint, NULL::bigint, u.pais,
              'primeira_vez_utc=' || to_char(u.primeira_vez_utc AT TIME ZONE 'UTC', {_UTC}),
              'hora=' || u.hora || '; dia_semana=' || u.dia_semana || '; semana=' || u.semana || '; fuso=' || d.fuso
       FROM (SELECT * FROM silver.fato_usuario WHERE pais = 'Brazil' ORDER BY md5(usuario_id) LIMIT 5) u
       JOIN silver.dim_pais d USING (pais)""",
    """INSERT INTO auditoria.antes_depois (execucao_id, tratamento, ordem, bronze_id, pais, antes, depois)
       SELECT %(e)s, 'texto_variaveis', (row_number() OVER (ORDER BY f.bronze_id))::smallint, f.bronze_id, f.pais,
              'conversation[1].content=' || length(b.conversation->0->>'content') || ' chars; conversation[2].content='
                || length(b.conversation->1->>'content') || ' chars',
              'prompt1_chars=' || f.prompt1_chars || '; tema=' || t.tema || '; recusa=' || f.recusa
       FROM (SELECT bronze_id, pais, prompt1_chars, tema_id, recusa FROM silver.fato_conversa WHERE pais = 'Brazil'
             ORDER BY md5(bronze_id::text) LIMIT 5) f
       JOIN bronze.wildchat b USING (bronze_id)
       LEFT JOIN silver.dim_tema t USING (tema_id)""",
]


def auditar_silver(dw, exec_id: int) -> dict:
    """Dentro da transacao `dw`, logo depois de construir a silver. Devolve um resumo para o log do ETL."""
    p = {"e": exec_id}
    with dw.cursor() as cur:
        # so a ULTIMA carga fica (o historico das cargas esta em ops.etl_execucao); na mesma transacao: se a carga falhar, volta o anterior
        cur.execute("""TRUNCATE auditoria.fluxo_pais, auditoria.nulos,
                       auditoria.registro_excluido, auditoria.antes_depois""")
        cur.execute(SQL_EXCLUIDOS, p)
        cur.execute(SQL_FLUXO, p)
        cur.execute(SQL_FLUXO_TOTAL, p)
        for ordem, (codigo, col_b, col_s, sql_b, sql_s, acao, tratamento) in enumerate(NULOS, 1):
            lb, nb = cur.execute(sql_b).fetchone()
            ls, ns = cur.execute(sql_s).fetchone() if sql_s else (None, None)
            cur.execute("""INSERT INTO auditoria.nulos (execucao_id, ordem, codigo, coluna_bronze, coluna_silver, linhas_bronze,
                           nulos_bronze, linhas_silver, nulos_silver, acao, tratamento) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (exec_id, ordem, codigo, col_b, col_s, lb, nb, ls, ns, acao, tratamento))
        for sql in SQLS_ANTES_DEPOIS:
            cur.execute(sql, p)
        excluidas = cur.execute("SELECT count(*) FROM auditoria.registro_excluido WHERE execucao_id = %s", (exec_id,)).fetchone()[0]
        exemplos = cur.execute("SELECT count(*) FROM auditoria.antes_depois WHERE execucao_id = %s", (exec_id,)).fetchone()[0]
    return {"excluidas": excluidas, "exemplos_antes_depois": exemplos}
