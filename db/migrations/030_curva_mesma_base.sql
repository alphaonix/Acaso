-- Curva de retorno na mesma base dos cartoes: o ponto de d dias usa quem tem janela completa de max(d, 7) dias, entao os
-- pontos de 24 h e 7 dias batem com os cartoes (pessoas elegiveis). `voltaram_janela30` guarda, so para a nota "da quem volta em
-- ate 30 dias, quantos voltaram na 1a semana", quem voltou ate d dias ENTRE as pessoas com 30 dias completos (base do ponto de 30 dias).
ALTER TABLE gold.agg_curva_retorno ADD COLUMN voltaram_janela30 integer NOT NULL DEFAULT 0;
COMMENT ON TABLE gold.agg_curva_retorno IS '% que ja voltou (2a sessao) ate N dias; base do ponto = pessoas com janela completa de max(N, 7) dias';