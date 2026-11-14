-- HISTORICO DE METRICAS POR CAMADA (prevencao de divergencias). Diferente das outras tabelas de `auditoria` (que guardam so a ULTIMA
-- carga), esta guarda TODAS as cargas: assim da para ver quando um numero mudou e comparar duas cargas.
-- Cada carga grava, por camada (bronze, silver, gold), contagens, vazios, distribuicoes e "impressoes digitais" (somas de hashes) do conteudo.
CREATE TABLE auditoria.metrica (
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao (id),
  camada text NOT NULL,                  -- bronze | silver | gold
  metrica text NOT NULL,                 -- ex.: linhas, nulos, pessoas_elegiveis, impressao_pessoas
  escopo text NOT NULL DEFAULT '',       -- ex.: arquivo, pais, tabela, coluna
  valor numeric,                         -- numero (contagens, taxas)
  texto text,                            -- impressao digital do conteudo (soma de hashes) ou periodo
  PRIMARY KEY (execucao_id, camada, metrica, escopo)
);

-- Todas as metricas, com o horario e o resultado da carga: para investigar "quando esse numero mudou?".
CREATE VIEW auditoria.historico_metrica AS
SELECT e.id AS execucao_id, e.iniciado_em, e.status, m.camada, m.metrica, m.escopo, m.valor, m.texto
FROM auditoria.metrica m JOIN ops.etl_execucao e ON e.id = m.execucao_id;

-- O que mudou entre as duas ULTIMAS cargas bem-sucedidas (status ok ou alerta). Vazia = nada mudou.
CREATE VIEW auditoria.mudancas_entre_cargas AS
WITH validas AS (
  SELECT e.id, row_number() OVER (ORDER BY e.id DESC) AS ordem
  FROM ops.etl_execucao e
  WHERE e.status IN ('ok', 'alerta') AND EXISTS (SELECT 1 FROM auditoria.metrica m WHERE m.execucao_id = e.id)
), nova AS (SELECT id FROM validas WHERE ordem = 1), velha AS (SELECT id FROM validas WHERE ordem = 2)
SELECT (SELECT id FROM velha) AS carga_antes, (SELECT id FROM nova) AS carga_depois,
       n.camada, n.metrica, n.escopo, v.valor AS valor_antes, n.valor AS valor_depois, v.texto AS texto_antes, n.texto AS texto_depois
FROM auditoria.metrica n
JOIN auditoria.metrica v USING (camada, metrica, escopo)
WHERE n.execucao_id = (SELECT id FROM nova) AND v.execucao_id = (SELECT id FROM velha)
  AND (n.valor IS DISTINCT FROM v.valor OR n.texto IS DISTINCT FROM v.texto);

COMMENT ON TABLE auditoria.metrica IS 'Historico (todas as cargas) de contagens, vazios, distribuicoes e impressoes digitais por camada.';
COMMENT ON VIEW auditoria.mudancas_entre_cargas IS 'Metricas que mudaram entre as duas ultimas cargas bem-sucedidas. Vazia = nada mudou.';
