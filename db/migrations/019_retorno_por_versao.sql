-- Retorno em 7 dias por versao do modelo da 1a conversa (so elegiveis), ao lado da recusa por versao.
ALTER TABLE gold.agg_recusa_modelo ADD COLUMN IF NOT EXISTS elegiveis integer NOT NULL DEFAULT 0;
ALTER TABLE gold.agg_recusa_modelo ADD COLUMN IF NOT EXISTS voltaram_7d integer NOT NULL DEFAULT 0;