-- Graficos do front: uso por dia e retorno por mes x fator (para a decomposicao mix x taxa). Gold, calculado pelo ETL.
CREATE TABLE gold.agg_uso_dia (
  pais text NOT NULL, dia date NOT NULL, conversas integer NOT NULL, usuarios_ativos integer NOT NULL,
  PRIMARY KEY (pais, dia)
);
COMMENT ON TABLE gold.agg_uso_dia IS 'Conversas e usuarios distintos por dia local do pais.';
CREATE TABLE gold.agg_retorno_mes_fator (
  pais text NOT NULL, mes date NOT NULL, fator text NOT NULL, nivel text NOT NULL,
  elegiveis integer NOT NULL, voltaram_7d integer NOT NULL,
  PRIMARY KEY (pais, mes, fator, nivel)
);
COMMENT ON TABLE gold.agg_retorno_mes_fator IS 'Usuarios elegiveis e que voltaram, por mes da primeira vez (fuso do pais), fator e nivel. Base da decomposicao mix x taxa.';