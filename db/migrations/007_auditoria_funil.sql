-- A auditoria passa a guardar SO A ULTIMA CARGA (o ETL esvazia estas tabelas a cada carga): assim `SELECT * FROM auditoria.x` mostra
-- sempre uma carga so, sem misturar execucoes. O historico das cargas continua em ops.etl_execucao e ops.qa_resultado.
-- E ha uma visao `auditoria.funil` que conta a historia na ordem (bronze -> excluidas -> silver -> gold) com a conferencia ao lado,
-- porque NAO se compara a soma das tabelas de uma camada: elas tem granularidades diferentes (conversa, usuario, resumo).
ALTER TABLE auditoria.contagem_camada ADD COLUMN descricao text NOT NULL DEFAULT '';

CREATE VIEW auditoria.funil AS
SELECT f.execucao_id, f.pais, v.ordem, v.camada, v.etapa, v.unidade, v.linhas, v.confere, v.explicacao
FROM auditoria.fluxo_pais f
CROSS JOIN LATERAL (VALUES
  (1, 'bronze',          'Linhas brutas',            'conversas', f.bronze_linhas, NULL::boolean,
      'Dado como veio'),
  (2, 'bronze > silver', 'Excluidas na limpeza',     'conversas', -(f.excl_sem_inicio + f.excl_sem_ip + f.excl_duplicadas), NULL::boolean,
      'Sem inicio, sem IP ou duplicata exata (veja auditoria.registro_excluido)'),
  (3, 'silver',          'Conversas na silver',      'conversas', f.silver_conversas,
      f.silver_conversas = f.bronze_linhas - (f.excl_sem_inicio + f.excl_sem_ip + f.excl_duplicadas),
      'Deve ser igual a: bronze menos excluidas'),
  (4, 'silver',          'Usuarios na silver',       'usuarios',  f.silver_usuarios, NULL::boolean,
      'Conversas agrupadas por usuario: e agrupamento, nao perda de linhas'),
  (5, 'gold',            'Usuarios na gold (tela)',  'usuarios',  f.gold_usuarios, f.gold_usuarios = f.silver_usuarios,
      'Deve ser igual aos usuarios da silver'),
  (6, 'gold',            'Conversas na gold (tela)', 'conversas', f.gold_conversas, f.gold_conversas = f.silver_conversas,
      'Deve ser igual as conversas da silver')
) AS v(ordem, camada, etapa, unidade, linhas, confere, explicacao);

GRANT SELECT ON auditoria.funil TO api_ro;
COMMENT ON SCHEMA auditoria IS 'Linhagem entre camadas da ULTIMA carga: contagens, funil, excluidas, nulos, antes/depois. Historico das cargas: ops.etl_execucao.';
COMMENT ON VIEW auditoria.funil IS 'O caminho do dado, por pais: bronze -> excluidas -> silver -> gold, com a conferencia (confere) em cada passo.';
