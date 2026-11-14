"""CAMADA SILVER: o dado limpo, com as regras de negocio aplicadas. NAO guarda texto de conversa nem endereco de internet.

  construir_silver(dw)         esvazia, limpa, define a "pessoa", as visitas, o retorno, a elegibilidade, o tema e a recusa
  auditar_silver(dw, exec_id)  registra o que foi excluido e por que (schema auditoria)
  validar_silver(dw, exec_id)  confere bronze = silver + excluidas, recalcula o retorno e compara com os numeros validados
Arquivos desta pasta:  limpar.py  sql.py  construir.py  auditoria.py  validar.py  (explicacao em LEIA-ME.md)
"""
from .auditoria import auditar_silver
from .construir import construir_silver
from .limpar import limpar_silver
from .validar import validar_silver

__all__ = ["construir_silver", "auditar_silver", "validar_silver", "limpar_silver"]
