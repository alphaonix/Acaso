-- Foto de perfil (URL) mostrada no avatar do topo. Opcional.
ALTER TABLE ops.usuario_dashboard ADD COLUMN IF NOT EXISTS foto_url text;
