-- Arquitetura em camadas (ADR-004). Bronze = Parquet imutavel (fora do banco; so o registro dos lotes fica em ops).
--   silver: dados limpos, deduplicados, com as definicoes aplicadas (BDR-001/003). Sem texto de conversa.
--   gold:   agregados, efeitos e catalogo prontos para a tela. E o UNICO schema que a API enxerga (alem de ops).
--   ops:    operacao do ETL (execucoes, lotes da bronze, resultados de qualidade).
CREATE SCHEMA silver;
CREATE SCHEMA gold;
CREATE SCHEMA ops;

-- ops ---------------------------------------------------------------------------------------------------
CREATE TABLE ops.etl_execucao (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  iniciado_em timestamptz NOT NULL DEFAULT now(), finalizado_em timestamptz,
  status text NOT NULL DEFAULT 'rodando',          -- rodando | ok | alerta | falhou | erro
  versao_codigo text, linhas_lidas bigint, linhas_carregadas bigint, observacao text
);
CREATE TABLE ops.bronze_lote (                      -- linhagem: de qual arquivo veio cada carga
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao,
  arquivo text NOT NULL, sha256 text NOT NULL, linhas bigint NOT NULL, tamanho_bytes bigint NOT NULL,
  registrado_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ops.qa_resultado (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao, verificacao text NOT NULL,
  esperado text, obtido text, passou boolean NOT NULL, criado_em timestamptz NOT NULL DEFAULT now()
);

-- silver ------------------------------------------------------------------------------------------------
CREATE TABLE silver.dim_pais (
  pais text PRIMARY KEY,                            -- country do WildChat; nulo vira 'Desconhecido'
  nome_exibicao text NOT NULL,
  fuso text NOT NULL,                               -- fuso IANA em que o "dia" e a "semana" sao contados
  fuso_aproximado boolean NOT NULL,                 -- true = pais com varios fusos ou sem mapeamento (premissa)
  idioma_padrao text NOT NULL DEFAULT 'en',
  tem_texto boolean NOT NULL                        -- true = tema/recusa/tamanhos disponiveis (so Brasil na semente)
);
CREATE TABLE silver.dim_tema (tema_id smallint PRIMARY KEY, tema text NOT NULL);

CREATE TABLE silver.fato_conversa (                 -- 1 linha por conversa; sem texto
  conversa_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  conversation_hash text NOT NULL,
  usuario_id text NOT NULL,
  pais text NOT NULL REFERENCES silver.dim_pais,
  estado text,
  modelo text NOT NULL,
  idioma text,
  turnos integer NOT NULL,
  inicio_utc timestamptz NOT NULL,                  -- 1a resposta do assistente (proxy de inicio; BDR-001)
  fim_utc timestamptz NOT NULL,
  duracao_s integer,
  prompt1_chars integer, resp1_chars integer,       -- NULL fora dos paises com texto
  recusa boolean,
  tema_id smallint REFERENCES silver.dim_tema,
  redigida boolean,
  UNIQUE (conversation_hash, usuario_id, inicio_utc)
);
CREATE INDEX ix_fato_conversa_pais_inicio ON silver.fato_conversa (pais, inicio_utc);
CREATE INDEX ix_fato_conversa_usuario ON silver.fato_conversa (usuario_id);

CREATE TABLE silver.fato_usuario (                  -- 1 linha por usuario: 1a experiencia + desfecho
  usuario_id text NOT NULL,
  pais text NOT NULL REFERENCES silver.dim_pais,
  primeira_vez_utc timestamptz NOT NULL,
  semana date NOT NULL,                             -- segunda-feira da semana, no fuso do pais
  hora smallint NOT NULL,                           -- hora local (0-23)
  dia_semana smallint NOT NULL,                     -- 1=segunda ... 7=domingo (local)
  modelo text NOT NULL, idioma text, navegador text, sistema text, estado text, turnos integer NOT NULL,
  prompt1_chars integer, resp1_chars integer, recusa boolean,
  tema_id smallint REFERENCES silver.dim_tema,
  convs_1a_sessao integer NOT NULL, convs_total integer NOT NULL,
  voltou_7d boolean NOT NULL,
  elegivel boolean NOT NULL,                        -- janela de 7 dias completa e fora do periodo de lavagem
  PRIMARY KEY (usuario_id, pais)
);
CREATE INDEX ix_fato_usuario_pais_semana ON silver.fato_usuario (pais, semana);

-- gold --------------------------------------------------------------------------------------------------
CREATE FUNCTION gold.wilson_lo(k numeric, n numeric) RETURNS numeric LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN n > 0 THEN ((k/n + 1.96^2/(2*n)) - 1.96*sqrt((k/n)*(1-k/n)/n + 1.96^2/(4*n*n))) / (1 + 1.96^2/n) END $$;
CREATE FUNCTION gold.wilson_hi(k numeric, n numeric) RETURNS numeric LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN n > 0 THEN ((k/n + 1.96^2/(2*n)) + 1.96*sqrt((k/n)*(1-k/n)/n + 1.96^2/(4*n*n))) / (1 + 1.96^2/n) END $$;

CREATE TABLE gold.pais (                            -- o que o seletor de pais mostra
  pais text PRIMARY KEY, nome_exibicao text NOT NULL, fuso text NOT NULL, fuso_aproximado boolean NOT NULL,
  idioma_padrao text NOT NULL, tem_texto boolean NOT NULL,
  usuarios integer NOT NULL, usuarios_elegiveis integer NOT NULL, conversas integer NOT NULL,
  primeira_data date, ultima_data date
);
CREATE TABLE gold.agg_retorno_semana (
  pais text NOT NULL, semana date NOT NULL,
  novos integer NOT NULL, elegiveis integer NOT NULL, voltaram_7d integer NOT NULL,
  taxa numeric, ic_lo numeric, ic_hi numeric,       -- IC 95% de Wilson; NULL se elegiveis < amostra minima
  PRIMARY KEY (pais, semana)
);
CREATE TABLE gold.agg_retorno_fator (
  pais text NOT NULL, fator text NOT NULL, nivel text NOT NULL,
  elegiveis integer NOT NULL, voltaram_7d integer NOT NULL,
  taxa numeric, ic_lo numeric, ic_hi numeric,
  PRIMARY KEY (pais, fator, nivel)
);
CREATE TABLE gold.efeito_fator (                    -- etapa de estimacao (BDR-004): efeito no retorno em 7 dias, em pontos percentuais
  pais text NOT NULL, fator text NOT NULL, contraste text NOT NULL,
  tipo text NOT NULL,                               -- 'alavanca' (produto controla) ou 'perfil' (descreve quem chega)
  n integer NOT NULL, n_tratados integer NOT NULL, n_controle integer NOT NULL,
  taxa_controle numeric NOT NULL,                   -- retorno do grupo de comparacao (0-1)
  efeito_bruto_pp numeric NOT NULL, bruto_ic_lo numeric NOT NULL, bruto_ic_hi numeric NOT NULL,   -- sem ajuste
  efeito_pp numeric NOT NULL, ic_lo numeric NOT NULL, ic_hi numeric NOT NULL,                      -- ajustado, IC 95%
  sobreposicao numeric NOT NULL,                    -- % de usuarios com probabilidade de tratamento entre 5% e 95%
  e_value numeric NOT NULL, e_value_ic numeric NOT NULL,   -- forca minima de um confundidor nao medido para anular
  metodo text NOT NULL, ajustado_por text NOT NULL,
  PRIMARY KEY (pais, fator, contraste)
);
CREATE TABLE gold.catalogo_indicador (              -- definicoes unicas: tooltip, glossario, abertura, README e testes (BDR-002)
  indicador_id text PRIMARY KEY, nome text NOT NULL, pergunta text NOT NULL,
  unidade text NOT NULL, denominador text NOT NULL, formula text NOT NULL, sql_referencia text NOT NULL,
  fonte text NOT NULL, periodo_referencia text NOT NULL, amostra_minima integer NOT NULL
);
