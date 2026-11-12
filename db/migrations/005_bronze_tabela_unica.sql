-- BRONZE em UMA tabela so: o WildChat-1M inteiro (todos os paises), como veio. Substitui as duas tabelas da migracao 004.
-- Linhas dos paises sem texto (semente "outros paises") ficam com conversation e moderacoes NULL; `arquivo_origem` diz de qual
-- arquivo da semente cada linha veio (e liga a ops.bronze_lote). Consulte:  SELECT * FROM bronze.wildchat LIMIT 100;
-- ATENCAO: as linhas do Brasil contem o TEXTO das conversas; so o ETL acessa o schema bronze (a API nao tem privilegio nenhum aqui).
CREATE TABLE bronze.wildchat (
  bronze_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- ordem de carga (reinicia a cada carga)
  conversation_hash text,
  model text,
  "timestamp" timestamptz,                       -- horario do ULTIMO turno (UTC)
  turn integer,
  language text,
  country text,
  state text,
  hashed_ip text,
  header jsonb,                                  -- {"user-agent": ..., "accept-language": ...}
  toxic boolean,
  redacted boolean,
  conversation jsonb,                            -- lista de mensagens (role, content = TEXTO, timestamp, ...). NULL fora do Brasil
  openai_moderation jsonb,                       -- NULL fora do Brasil
  detoxify_moderation jsonb,                     -- NULL fora do Brasil
  primeira_resposta_ts timestamptz,              -- so nas linhas sem texto: extraida da conversa ao gerar a semente (make_seed.py)
  arquivo_origem text NOT NULL                   -- wildchat_brasil.parquet | wildchat_outros_paises.parquet
);
CREATE INDEX ix_bronze_wildchat_hash ON bronze.wildchat (conversation_hash);
CREATE INDEX ix_bronze_wildchat_pais ON bronze.wildchat (country);
COMMENT ON TABLE bronze.wildchat IS 'WildChat-1M bruto, todos os paises (Brasil com texto; demais so metadados). Origem: ops.bronze_lote.';

DROP TABLE bronze.wildchat_brasil;
DROP TABLE bronze.wildchat_outros_paises;
UPDATE ops.bronze_lote SET tabela_destino = 'bronze.wildchat';
