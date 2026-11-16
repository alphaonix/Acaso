# ADR-007: contas de acesso criadas por migração

Status: aceita (16/11/2026).

## Contexto
O painel exige login. O repositório será público e não pode ter senha em texto. Quem avalia deve subir tudo com um comando, sem criar `.env`.

## Opções
1. **Conta e senha no `.env`.** Nada no repositório, mas exige configuração e o `.env` não vai junto.
2. **Senha aleatória no primeiro `up`, mostrada no log.** Sem segredo no repositório, mas obriga a procurar a senha no log.
3. **Contas de quem avalia numa migração, só com o hash da senha.** Funciona sem configurar nada.

## Decisão
Opção 3: `db/migrations/029_contas_avaliadoras.sql` cria as contas da Nathália e da Daniele com o hash scrypt (sal próprio de cada conta). A senha está no README.
- A API só verifica o hash (`backend/app/seguranca.py`). Sessão em cookie HttpOnly (JWT), com limite de 5 falhas em 5 minutos. O segredo da sessão é aleatório a cada subida.
- Sem `.env`: o código de contas pelo ambiente foi removido.

## Consequências
- Como a base é pública e o painel roda na máquina de quem o sobe, o login demonstra autenticação e não protege dado sensível. A senha é simples e o hash no repositório público tem pouco valor.
- Para trocar uma conta ou senha é preciso criar uma migração e recriar o banco.
- Em produção seria um provedor de identidade (Amazon Cognito).
