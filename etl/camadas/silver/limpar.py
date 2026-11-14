"""Esvazia a SILVER antes de reconstrui-la (dentro da transacao: se a carga falhar, os dados antigos voltam).
As quatro tabelas vao num unico TRUNCATE porque se referenciam entre si (chaves estrangeiras)."""


def limpar_silver(dw) -> None:
    with dw.cursor() as cur:
        cur.execute("TRUNCATE silver.fato_conversa, silver.fato_usuario, silver.dim_tema, silver.dim_pais RESTART IDENTITY")
