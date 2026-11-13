-- Retorno em 7 dias com e sem as 10 pessoas mais ativas (prova de que o uso concentrado nao move o indicador principal).
ALTER TABLE gold.pais
  ADD COLUMN voltaram_7d integer,                -- elegiveis que voltaram em 7 dias (todos)
  ADD COLUMN elegiveis_sem_top10 integer,        -- elegiveis fora das 10 pessoas mais ativas (por numero de conversas)
  ADD COLUMN voltaram_sem_top10 integer;         -- quantos deles voltaram em 7 dias
