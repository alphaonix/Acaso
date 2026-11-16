"""CAMADA BRONZE: o dado bruto, como veio, numa tabela do Postgres (bronze.wildchat). Nada e limpo nem calculado aqui.

  construir_bronze(...)  registra os arquivos da semente (sha256), esvazia a tabela e carrega os Parquet (DuckDB -> CSV -> COPY)
  validar_bronze(...)    confere que o que entrou bate com os arquivos de origem
Arquivos desta pasta:  registrar_lotes.py  limpar.py  carregar.py  validar.py  (explicacao no README da raiz, secao 4)
"""
from pathlib import Path

from .carregar import TABELA, carregar
from .contrato import ContratoQuebrado, exigir_contrato, verificar_contrato
from .diagnosticar import diagnosticar_bronze
from .limpar import limpar_bronze
from .registrar_lotes import registrar_lotes
from .validar import validar_bronze

__all__ = ["construir_bronze", "validar_bronze", "diagnosticar_bronze", "limpar_bronze", "carregar", "registrar_lotes", "TABELA",
           "verificar_contrato", "exigir_contrato", "ContratoQuebrado"]


def construir_bronze(ops, dw, con, exec_id: int, semente: Path) -> dict[str, int]:
    """0) confere o contrato da semente  1) registra os arquivos (ops, automatica)  2) esvazia a bronze (dw, transacao)  3) carrega.
    Devolve as linhas por arquivo."""
    exigir_contrato(con, semente)
    registrar_lotes(ops, con, exec_id, semente)
    limpar_bronze(dw)
    return carregar(dw, con, semente)
