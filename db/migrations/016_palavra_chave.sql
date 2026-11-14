-- Nuvem de palavras do 1o pedido: por palavra-chave (lista FIXA, etl/comum/definicoes.py), quantos usuarios a usaram no 1o pedido
-- e o retorno em 7 dias entre os elegiveis. So existe onde ha texto (Brasil). Nunca guarda texto livre.
CREATE TABLE gold.palavra_chave (
  pais text NOT NULL, palavra text NOT NULL, usuarios integer NOT NULL, elegiveis integer NOT NULL, voltaram_7d integer NOT NULL,
  PRIMARY KEY (pais, palavra)
);
COMMENT ON TABLE gold.palavra_chave IS 'Usuarios por palavra-chave (lista fixa) no 1o pedido e retorno em 7 dias entre os elegiveis.';