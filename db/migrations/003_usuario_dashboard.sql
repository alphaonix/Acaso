-- Contas de acesso ao dashboard. A senha NUNCA fica em texto: so o hash (scrypt). As contas vem de uma migracao (029);
-- em producao seria um provedor de identidade (ex.: Amazon Cognito).
CREATE TABLE ops.usuario_dashboard (
  email text PRIMARY KEY,
  nome text NOT NULL,
  senha_hash text NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON ops.usuario_dashboard TO api_ro;
