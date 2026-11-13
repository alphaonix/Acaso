-- Voltou em 24 h sobre a MESMA base do retorno em 7 dias (elegiveis), para os dois numeros da Visao geral serem comparaveis.
ALTER TABLE gold.pais ADD COLUMN voltaram_24h integer;   -- elegiveis que voltaram em ate 24 h
