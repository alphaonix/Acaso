-- ALERTA SEMANAL: semanas com pico de "novos" ou salto da taxa, comparadas com as 6 semanas anteriores da propria carga (comum/anomalia_semanal.py).
-- Nasceu do incidente do PDF (4.2): os novos de UMA semana quase dobraram sem ninguem voltar a mais, e a media do pais escondia isso.
-- `nova` = a semana e um alerta NOVO desde a carga anterior (o que ja existia nos dados e conhecido e nao reprova a conferencia).
CREATE TABLE auditoria.anomalia_semanal (
  id bigserial PRIMARY KEY,
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao (id),
  pais text NOT NULL,
  semana date NOT NULL,
  diagnostico text NOT NULL,        -- PESSOA_DIVIDIDA | DENOMINADOR_INFLADO | PICO_DE_USO | QUEDA_DE_NOVOS | TAXA_SEMANAL
  camada text NOT NULL,             -- SILVER | SILVER_OU_BRONZE | BRONZE | SEM_CAUSA
  novos int NOT NULL, novos_base numeric NOT NULL,
  voltaram int NOT NULL, voltaram_base numeric NOT NULL,
  taxa numeric, taxa_base numeric,
  pct_endereco numeric, pct_endereco_base numeric,   -- % dos "novos" com endereco que ja aparecia antes (pista de pessoa dividida)
  resumo text NOT NULL,
  nova boolean NOT NULL DEFAULT false,
  UNIQUE (execucao_id, pais, semana, diagnostico)
);
COMMENT ON TABLE auditoria.anomalia_semanal IS 'Semanas com pico de novos ou salto da taxa, com o diagnostico e a camada provavel.';
