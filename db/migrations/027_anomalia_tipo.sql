-- Dois tipos de anomalia: TAXA (a taxa de retorno saltou) e ENTRADA (a taxa quase nao mexeu, mas o dado de entrada mudou de padrao,
-- por exemplo 60% das linhas sem endereco). Descoberto pela simulacao de cenarios: olhar so a taxa deixava passar um defeito da fonte.
ALTER TABLE auditoria.anomalia ADD COLUMN tipo text NOT NULL DEFAULT 'TAXA';
COMMENT ON COLUMN auditoria.anomalia.tipo IS 'TAXA: a taxa saltou | ENTRADA: o dado de entrada mudou de padrao sem a taxa mudar';
