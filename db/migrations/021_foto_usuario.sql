-- Foto de perfil (URL) mostrada no avatar do topo. Opcional; vem de DASH_USERS ('email|Nome|url'), fora do repositorio.
ALTER TABLE ops.usuario_dashboard ADD COLUMN IF NOT EXISTS foto_url text;
