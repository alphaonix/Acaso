-- A API usa um papel SOMENTE LEITURA que enxerga so gold (e ops, para saude e qualidade).
-- Nao ha acesso a silver (dados por usuario) nem a bronze (que nem esta no banco). Ver ADR-004.
-- Em producao (RDS) a senha vem do AWS Secrets Manager; aqui o padrao e o do compose (.env.example).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'api_ro') THEN
    CREATE ROLE api_ro LOGIN PASSWORD 'api_ro';
  END IF;
END $$;
GRANT USAGE ON SCHEMA gold, ops TO api_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA gold, ops TO api_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO api_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT SELECT ON TABLES TO api_ro;
