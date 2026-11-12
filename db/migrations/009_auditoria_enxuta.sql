-- Limpeza: auditoria.camadas (uma linha por camada, em conversas) substitui a contagem por tabela e o funil.
DROP VIEW IF EXISTS auditoria.funil;
DROP TABLE IF EXISTS auditoria.contagem_camada;
COMMENT ON SCHEMA auditoria IS 'Linhagem entre camadas da ULTIMA carga: camadas (visao), fluxo por pais, excluidas, nulos, antes/depois. Historico das cargas: ops.etl_execucao.';
