-- AUDITORIA E LINHAGEM ENTRE CAMADAS (ADR-005). Preenchido pelo ETL a cada carga; responde:
--   quantas linhas ha em cada camada? o que foi excluido de uma camada para a outra, e por que? quais valores vazios (nulos)
--   existiam e o que se fez com eles? como o dado era antes e como ficou? os numeros batem entre as camadas?
-- Nao contem texto de conversa nem IP: so contagens, nomes de coluna e identificadores tecnicos. Por isso a API pode le-lo.
CREATE SCHEMA auditoria;

-- Linhagem: cada conversa da silver sabe de qual linha da bronze veio.
ALTER TABLE silver.fato_conversa ADD COLUMN bronze_id bigint;
CREATE INDEX ix_fato_conversa_bronze ON silver.fato_conversa (bronze_id);

-- As conferencias passam a dizer em qual TRANSICAO entre camadas atuam.
ALTER TABLE ops.qa_resultado ADD COLUMN transicao text NOT NULL DEFAULT 'geral';

-- 1) Quantas linhas em cada tabela de cada camada
CREATE TABLE auditoria.contagem_camada (
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao,
  ordem smallint NOT NULL, camada text NOT NULL, tabela text NOT NULL, codigo text NOT NULL, linhas bigint NOT NULL,
  PRIMARY KEY (execucao_id, tabela)
);

-- 2) O funil por pais: bronze -> (excluidas) -> silver -> gold. A linha pais='(todos)' soma tudo.
CREATE TABLE auditoria.fluxo_pais (
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao, pais text NOT NULL,
  bronze_linhas bigint NOT NULL,
  excl_sem_inicio bigint NOT NULL, excl_sem_ip bigint NOT NULL, excl_duplicadas bigint NOT NULL,
  silver_conversas bigint NOT NULL, silver_usuarios bigint NOT NULL,
  gold_usuarios bigint NOT NULL, gold_conversas bigint NOT NULL,
  pais_tratado bigint NOT NULL,                      -- linhas cujo country era nulo (viram 'Desconhecido')
  PRIMARY KEY (execucao_id, pais)
);

-- 3) Valores vazios (nulos) antes (bronze) e depois (silver), e o que o ETL fez com cada coluna
CREATE TABLE auditoria.nulos (
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao,
  ordem smallint NOT NULL, codigo text NOT NULL, coluna_bronze text NOT NULL, coluna_silver text NOT NULL,
  linhas_bronze bigint, nulos_bronze bigint, linhas_silver bigint, nulos_silver bigint,
  acao text NOT NULL,                                -- preenchido | mantido | excluido | derivado | ignorado
  tratamento text NOT NULL,                          -- descricao em portugues (a tela traduz por `codigo`)
  PRIMARY KEY (execucao_id, codigo)
);

-- 4) As linhas EXCLUIDAS da bronze na passagem para a silver, uma a uma (so identificadores tecnicos)
CREATE TABLE auditoria.registro_excluido (
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao,
  bronze_id bigint NOT NULL, conversation_hash text, pais text,
  motivo text NOT NULL,                              -- sem_inicio | sem_ip | duplicata_exata
  mantida_bronze_id bigint,                          -- em duplicata: a linha que ficou no lugar desta
  PRIMARY KEY (execucao_id, bronze_id)
);

-- 5) Exemplos de ANTES e DEPOIS de cada tratamento (campo=valor; sem texto, sem IP)
CREATE TABLE auditoria.antes_depois (
  execucao_id bigint NOT NULL REFERENCES ops.etl_execucao,
  tratamento text NOT NULL, ordem smallint NOT NULL, bronze_id bigint, pais text, antes text NOT NULL, depois text NOT NULL,
  PRIMARY KEY (execucao_id, tratamento, ordem)
);

GRANT USAGE ON SCHEMA auditoria TO api_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA auditoria TO api_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA auditoria GRANT SELECT ON TABLES TO api_ro;
