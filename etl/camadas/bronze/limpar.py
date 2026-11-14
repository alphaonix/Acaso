"""Esvazia a BRONZE antes de recarregar (dentro da transacao: se a carga falhar, os dados antigos voltam)."""


def limpar_bronze(dw) -> None:
    with dw.cursor() as cur:
        cur.execute("TRUNCATE bronze.wildchat RESTART IDENTITY")
