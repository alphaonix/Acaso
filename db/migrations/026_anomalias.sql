-- ANOMALIAS DE TAXA: a cada carga, o ETL compara a taxa de retorno em 7 dias de cada pais com a da carga anterior. Quando ela salta ou cai
-- demais (>= 5 pontos percentuais e improvavel de ser acaso), grava aqui o pais, os numeros e a ORIGEM PROVAVEL (bronze, silver, gold,
-- transformacao ou sem causa tecnica), com o funil camada por camada em `sinais`. Ver comum/anomalia.py e docs/PREVENCAO_DE_DIVERGENCIAS.md.
CREATE TABLE auditoria.anomalia (
  id bigserial PRIMARY KEY,
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao (id),
  execucao_referencia bigint NOT NULL REFERENCES ops.etl_execucao (id),   -- a carga anterior usada na comparacao
  pais text NOT NULL,
  taxa_referencia numeric NOT NULL,
  taxa_atual numeric NOT NULL,
  elegiveis_referencia int NOT NULL,
  elegiveis_atual int NOT NULL,
  z numeric,                                                              -- nulo = diferenca "infinita" (variancia zero)
  origem text NOT NULL,                                                   -- BRONZE | SILVER | GOLD | TRANSFORMACAO | SEM_CAUSA
  resumo text NOT NULL,
  sinais jsonb NOT NULL DEFAULT '[]',                                     -- o funil: camada, etapa, antes, agora, suspeito
  UNIQUE (execucao_id, pais)
);
COMMENT ON TABLE auditoria.anomalia IS 'Paises cuja taxa de retorno mudou demais entre duas cargas, com a origem provavel (qual camada).';
