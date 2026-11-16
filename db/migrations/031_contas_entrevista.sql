-- Mais duas contas de acesso, criadas depois da 029 (que nao se edita). Mesmo desenho: nome, e-mail e foto publicos; da senha
-- so o hash (scrypt, com sal proprio de cada conta); a senha e a mesma das outras contas, combinada na entrega.
INSERT INTO ops.usuario_dashboard (email, nome, senha_hash, foto_url) VALUES
  ('edivaldo.bezerra@aca.so', 'Edivaldo Bezerra', 'scrypt$16384$8$1$b37ccae96e62be9f676268ab2e98be13$11dd4b84e4bd2f75e864e677c1e2f910988456cecb00e0f3246ca155633a9b81',
   'https://lh3.googleusercontent.com/a-/ALV-UjVUN4Wxqea8f5tmd0x2fdjF6vChGuaTi8OwM185RtD9Vmdsf9U=s48-c'),
  ('tiago.moraes@aca.so', 'Tiago Moraes', 'scrypt$16384$8$1$91dcf179673f12737ac850750551b286$e72bae597b7c9c8ad52b865048aaf256d0be78ae7fa4cc9fe69b4fd5cd7700ae',
   'https://lh3.googleusercontent.com/a-/ALV-UjV28n-h4EgH92Z74N-R55a9MoE0WP_w5HrsBSVkAaqKWKyeun_P=s48-c')
ON CONFLICT (email) DO UPDATE SET nome = EXCLUDED.nome, senha_hash = EXCLUDED.senha_hash, foto_url = EXCLUDED.foto_url;
