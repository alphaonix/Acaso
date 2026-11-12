-- Contas de acesso ao dashboard. A senha NUNCA fica em texto: so o hash (scrypt). O ETL cria a conta de avaliacao a
-- partir de DASH_EMAIL/DASH_PASSWORD; em producao seria um provedor de identidade (ex.: Amazon Cognito).
CREATE TABLE ops.usuario_dashboard (
  email text PRIMARY KEY,
  nome text NOT NULL,
  senha_hash text NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON ops.usuario_dashboard TO api_ro;
