"""CAMADA GOLD: os resumos que a tela le (a API so enxerga esta camada). Taxa e margem de erro so com 30 ou mais pessoas.

  construir_gold(dw)         esvazia e monta as tabelas de resumo (pais, retorno por semana e por fator, curva, uso, concentracao...)
  construir_efeitos(dw)      estima os efeitos ajustados (AIPW) e grava em gold.efeito_fator (so Brasil)
  auditar_gold(dw, exec_id)  completa o funil por pais com os numeros da gold
  validar_gold(dw, exec_id)  confere que as somas da gold batem com a silver e que os efeitos sao coerentes
Arquivos desta pasta:  limpar.py  sql.py  construir.py  efeitos.py  auditoria.py  validar.py  (explicacao em LEIA-ME.md)
"""
from .auditoria import auditar_gold
from .construir import construir_gold
from .diagnosticar import diagnosticar_gold
from .efeitos import construir_efeitos
from .limpar import limpar_gold
from .validar import validar_gold

__all__ = ["construir_gold", "construir_efeitos", "auditar_gold", "diagnosticar_gold", "validar_gold", "limpar_gold"]
