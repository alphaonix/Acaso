-- Contas de acesso das pessoas que avaliam o desafio (nome, e-mail e foto publicos). A senha NAO esta aqui: so o hash
-- (scrypt, com sal proprio de cada conta); a senha foi combinada na entrega. O painel roda local e a base e publica
-- (WildChat), entao o login existe para demonstrar autenticacao, nao para proteger dado sensivel.
-- Para trocar uma conta ou senha: nova migracao com o hash novo (README, secao Acesso).
INSERT INTO ops.usuario_dashboard (email, nome, senha_hash, foto_url) VALUES
  ('nathalia.anjos@aca.so', 'Nathália Anjos', 'scrypt$16384$8$1$a15fe122b92613947ea0447cdf6f3035$ee55e6eb9e44ff9dd2bdb2811ae5fe7dc3e32ade351c1a94def545e4c85a1680',
   'https://lh3.googleusercontent.com/a-/ALV-UjWwU1Prd93LqH0pAHInnLrMCPM6BKxh3OEWn0PCqd8zlqxt73fz=s40-p'),
  ('daniele.cardoso@aca.so', 'Daniele Cardoso', 'scrypt$16384$8$1$60024c8d08a0d71efda7616daf294850$80315c03fd18e3b16a933422291bd3f6ae0df2dc27e36516e8b18fb9eaa91da4',
   'https://lh3.googleusercontent.com/a-/ALV-UjXalKr7osD57DuhSKn_l81GLQAcb0XNiZEwYa955abZq1RWsrU=s40-p')
ON CONFLICT (email) DO UPDATE SET nome = EXCLUDED.nome, senha_hash = EXCLUDED.senha_hash, foto_url = EXCLUDED.foto_url;