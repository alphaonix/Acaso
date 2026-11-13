-- Retorno e conversas por versao do modelo para TODOS os paises; a recusa so existe onde ha texto (conversas_texto).
ALTER TABLE gold.agg_recusa_modelo ADD COLUMN IF NOT EXISTS conversas_texto integer NOT NULL DEFAULT 0;
