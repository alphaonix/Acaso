-- Uma linha por camada, TODAS NA MESMA UNIDADE (conversas), por pais: assim as camadas se comparam.
--   linhas        = conversas na camada
--   excluidas     = conversas que sairam da camada anterior no caminho (e os motivos, em colunas)
--   esperado      = conversas da camada anterior - excluidas
--   confere       = linhas = esperado
-- Para ver cada linha excluida: auditoria.registro_excluido.
DROP VIEW IF EXISTS auditoria.camadas;
CREATE VIEW auditoria.camadas AS
SELECT f.execucao_id, f.pais, v.ordem, v.camada, v.linhas, v.excluidas,
       v.excl_sem_inicio, v.excl_sem_ip, v.excl_duplicadas, v.esperado, v.linhas = v.esperado AS confere
FROM auditoria.fluxo_pais f
CROSS JOIN LATERAL (VALUES
  (1, 'bronze', f.bronze_linhas, 0, 0, 0, 0, f.bronze_linhas),
  (2, 'silver', f.silver_conversas,
      f.excl_sem_inicio + f.excl_sem_ip + f.excl_duplicadas, f.excl_sem_inicio, f.excl_sem_ip, f.excl_duplicadas,
      f.bronze_linhas - (f.excl_sem_inicio + f.excl_sem_ip + f.excl_duplicadas)),
  (3, 'gold',   f.gold_conversas, 0, 0, 0, 0, f.silver_conversas)
) AS v(ordem, camada, linhas, excluidas, excl_sem_inicio, excl_sem_ip, excl_duplicadas, esperado);

COMMENT ON VIEW auditoria.camadas IS
  'Conversas por camada (bronze, silver, gold), por pais, com as excluidas entre camadas e a conferencia.';
GRANT SELECT ON auditoria.camadas TO api_ro;
