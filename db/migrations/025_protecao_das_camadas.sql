-- PROTECAO DAS CAMADAS: bronze, silver e gold so mudam DURANTE uma carga do ETL.
-- 1) Trava: qualquer INSERT/UPDATE/DELETE/TRUNCATE nessas tabelas fora da carga e recusado (o ETL avisa que esta carregando com
--    `SET LOCAL etl.carga = 'on'`). Isso evita o acidente (alguem editar uma tabela no DBeaver, um script solto, uma carga "por fora").
--    Nao e defesa contra quem e dono do banco e desliga a trava de proposito: isso e pego pela verificacao de integridade (item 2).
-- 2) Selo e verificacao: auditoria.verificacao guarda cada conferencia "o estado atual das camadas e o que a ultima carga deixou?".
-- 3) Papel `auditor`: somente leitura, para consultar no DBeaver sem risco de alterar dado (o usuario `etl` e so do container).
CREATE OR REPLACE FUNCTION auditoria.bloquear_escrita_fora_do_etl() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF coalesce(current_setting('etl.carga', true), '') <> 'on' THEN
    RAISE EXCEPTION 'Camada protegida: % em %.% so e permitido ao ETL. Corrija a regra no codigo e rode a carga de novo.',
      TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NULL;
END $$;

-- Instala a trava em TODA tabela das tres camadas (inclusive as criadas por migracoes futuras). So cria onde falta: roda a cada carga.
CREATE OR REPLACE FUNCTION auditoria.proteger_camadas() RETURNS int LANGUAGE plpgsql AS $$
DECLARE t record; novas int := 0;
BEGIN
  FOR t IN SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('bronze', 'silver', 'gold') LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid = format('%I.%I', t.schemaname, t.tablename)::regclass AND tgname = 'protecao_camada') THEN
      EXECUTE format('CREATE TRIGGER protecao_camada BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON %I.%I FOR EACH STATEMENT EXECUTE FUNCTION auditoria.bloquear_escrita_fora_do_etl()',
                     t.schemaname, t.tablename);
      novas := novas + 1;
    END IF;
  END LOOP;
  RETURN novas;
END $$;

-- Cada tabela das camadas e se a trava esta ligada (tgenabled = 'O'). Qualquer linha com protegida = false e um alerta.
CREATE VIEW auditoria.protecao_camadas AS
SELECT t.schemaname AS camada, t.tablename AS tabela,
       EXISTS (SELECT 1 FROM pg_trigger g WHERE g.tgrelid = format('%I.%I', t.schemaname, t.tablename)::regclass
               AND g.tgname = 'protecao_camada' AND g.tgenabled = 'O') AS protegida
FROM pg_tables t WHERE t.schemaname IN ('bronze', 'silver', 'gold');

CREATE TABLE auditoria.verificacao (
  id bigserial PRIMARY KEY,
  feita_em timestamptz NOT NULL DEFAULT now(),
  origem text NOT NULL,                              -- antes_da_carga (o ETL confere antes de reconstruir) | manual
  carga_verificada bigint REFERENCES ops.etl_execucao (id),   -- a carga publicada contra a qual se comparou
  conferencias int NOT NULL,
  divergencias int NOT NULL,
  detalhe jsonb NOT NULL DEFAULT '[]'                -- as primeiras divergencias
);
COMMENT ON TABLE auditoria.verificacao IS 'Historico das verificacoes de integridade: o estado atual das camadas e o que a ultima carga publicada deixou?';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auditor') THEN
    CREATE ROLE auditor LOGIN PASSWORD 'auditor';
  END IF;
END $$;
GRANT USAGE ON SCHEMA bronze, silver, gold, ops, auditoria TO auditor;
GRANT SELECT ON ALL TABLES IN SCHEMA bronze, silver, gold, ops, auditoria TO auditor;
ALTER DEFAULT PRIVILEGES IN SCHEMA bronze GRANT SELECT ON TABLES TO auditor;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver GRANT SELECT ON TABLES TO auditor;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO auditor;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT SELECT ON TABLES TO auditor;
ALTER DEFAULT PRIVILEGES IN SCHEMA auditoria GRANT SELECT ON TABLES TO auditor;
