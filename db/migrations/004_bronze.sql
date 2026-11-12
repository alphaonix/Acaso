-- BRONZE: copia fiel e CONSULTAVEL do dado bruto (a semente em Parquet), uma tabela por arquivo de origem.
-- Nada e limpo nem derivado aqui; a silver e construida A PARTIR destas tabelas (ADR-004).
-- Consulte no DBeaver, por exemplo:  SELECT * FROM bronze.wildchat_brasil LIMIT 100;
-- ATENCAO: wildchat_brasil contem o TEXTO das conversas. Por isso so o ETL acessa o schema bronze; o papel da API nao tem
-- nenhum privilegio aqui (nem em silver).
CREATE SCHEMA bronze;

CREATE TABLE bronze.wildchat_brasil (            -- espelho de data/seed/wildchat_brasil.parquet (todas as colunas)
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
  conversation jsonb,                            -- lista de mensagens: role, content (TEXTO), timestamp, turn_identifier, ...
  openai_moderation jsonb,
  detoxify_moderation jsonb
);
CREATE INDEX ix_bronze_brasil_hash ON bronze.wildchat_brasil (conversation_hash);

CREATE TABLE bronze.wildchat_outros_paises (     -- espelho de data/seed/wildchat_outros_paises.parquet (SEM texto das conversas)
  conversation_hash text,
  model text,
  "timestamp" timestamptz,
  turn integer,
  language text,
  country text,
  state text,
  hashed_ip text,
  header jsonb,
  toxic boolean,
  redacted boolean,
  primeira_resposta_ts timestamptz               -- unica coluna extraida da conversa ao gerar a semente (make_seed.py)
);
CREATE INDEX ix_bronze_outros_pais ON bronze.wildchat_outros_paises (country);

COMMENT ON TABLE bronze.wildchat_brasil IS 'Bruto do Brasil, como veio do WildChat-1M (com texto). Origem: ops.bronze_lote.';
COMMENT ON TABLE bronze.wildchat_outros_paises IS 'Bruto dos demais paises, so metadados. Origem: ops.bronze_lote.';

-- Cada lote registrado em ops.bronze_lote aponta para a tabela onde foi carregado.
ALTER TABLE ops.bronze_lote ADD COLUMN tabela_destino text;

-- Funcao de apoio das regras de texto (tema, recusa): permite o mesmo SQL de definicoes.py no Postgres.
CREATE FUNCTION public.etl_rx(texto text, padrao text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$ SELECT texto ~ padrao $$;
