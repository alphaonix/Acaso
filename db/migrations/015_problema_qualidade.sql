-- Problemas de qualidade encontrados na base (tela "Glossario e qualidade"): contagens calculadas pelo ETL a cada carga.
-- O texto de cada problema/tratamento fica no frontend (por `codigo`, em PT e EN); aqui so os numeros.
CREATE TABLE gold.problema_qualidade (
  codigo text PRIMARY KEY, ordem integer NOT NULL,
  escopo text NOT NULL CHECK (escopo IN ('todos', 'brasil')),   -- 'brasil' = so o recorte com texto
  afetadas bigint NOT NULL, total bigint NOT NULL
);
COMMENT ON TABLE gold.problema_qualidade IS 'Conversas afetadas por cada problema de qualidade da base, sobre o total do escopo.';