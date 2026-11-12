-- Codigo ISO do pais (iso2): a tela escreve o nome do pais na lingua escolhida (PT/EN) a partir dele, para todos os paises.
ALTER TABLE silver.dim_pais ADD COLUMN iso2 text;
ALTER TABLE gold.pais ADD COLUMN iso2 text;
COMMENT ON COLUMN silver.dim_pais.iso2 IS 'ISO 3166-1 alfa-2; NULL so para Desconhecido.';