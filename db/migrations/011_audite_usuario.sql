-- "Audite um usuario": mostra, conversa a conversa, como a silver chegou em sessao, voltou_7d e elegivel para UM usuario.
-- Uso:  SELECT * FROM auditoria.audite_usuario('00a3cf656f92');
-- Os limites (30 min de sessao e 7 dias de janela) sao os mesmos de etl/comum/definicoes.py; horarios no fuso do pais.
CREATE OR REPLACE FUNCTION auditoria.audite_usuario(p_usuario text)
RETURNS TABLE (n int, pais text, inicio_local timestamp, fim_local timestamp, min_desde_fim_anterior int, sessao int,
               dias_desde_a_primeira numeric, dentro_da_janela_7d boolean, voltou_7d_silver boolean, elegivel_silver boolean)
LANGUAGE sql STABLE AS $$
  WITH c AS (SELECT f.*, d.fuso FROM silver.fato_conversa f JOIN silver.dim_pais d ON d.pais = f.pais WHERE f.usuario_id = p_usuario),
  o AS (SELECT c.*, row_number() OVER w AS ordem, lag(c.fim_utc) OVER w AS fim_anterior
        FROM c WINDOW w AS (PARTITION BY c.pais ORDER BY c.inicio_utc, c.fim_utc)),
  s AS (SELECT o.*, sum(CASE WHEN o.fim_anterior IS NULL OR o.inicio_utc - o.fim_anterior > INTERVAL '30 minutes' THEN 1 ELSE 0 END)
                      OVER (PARTITION BY o.pais ORDER BY o.ordem) AS nsessao,
               min(o.inicio_utc) OVER (PARTITION BY o.pais) AS primeira FROM o)
  SELECT s.ordem::int, s.pais, timezone(s.fuso, s.inicio_utc), timezone(s.fuso, s.fim_utc),
         round(extract(epoch FROM s.inicio_utc - s.fim_anterior) / 60)::int, s.nsessao::int,
         round(extract(epoch FROM s.inicio_utc - s.primeira) / 86400, 2),
         s.nsessao > 1 AND s.inicio_utc <= s.primeira + INTERVAL '7 days',
         u.voltou_7d, u.elegivel
  FROM s JOIN silver.fato_usuario u ON u.usuario_id = p_usuario AND u.pais = s.pais
  ORDER BY s.ordem
$$;
COMMENT ON FUNCTION auditoria.audite_usuario(text) IS 'Passo a passo de um usuario: conversas, intervalos, sessoes, janela de 7 dias e as marcacoes da silver.';