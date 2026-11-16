"""Autenticacao: verificacao de senha (scrypt), sessao em JWT num cookie HttpOnly e limite de tentativas de login."""
import hashlib
import hmac
import os
import secrets
import time

import jwt

# Sem SESSION_SECRET (ou com o valor antigo de exemplo), gera um segredo aleatorio a cada subida: nao existe chave padrao conhecida
# que permita forjar uma sessao. Efeito: reiniciar a API encerra as sessoes. Em producao o segredo vem do Secrets Manager.
SEGREDO = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
if SEGREDO == "dev-troque-em-producao":
    SEGREDO = secrets.token_hex(32)
COOKIE = "sessao"
EXPIRA_S = 8 * 3600
COOKIE_SEGURO = os.environ.get("COOKIE_SECURE", "0") == "1"   # 1 atras de HTTPS (CloudFront/ALB)
_HASH_FALSO = "scrypt$16384$8$1$" + "00" * 16 + "$" + "00" * 32   # gasta o mesmo tempo quando o e-mail nao existe


def verificar_senha(senha: str, armazenado: str | None) -> bool:
    try:
        _, n, r, p, sal, h = (armazenado or _HASH_FALSO).split("$")
        esperado = bytes.fromhex(h)
        calc = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p), dklen=len(esperado))
        return armazenado is not None and hmac.compare_digest(calc, esperado)
    except (ValueError, TypeError):
        return False


def criar_token(email: str, nome: str) -> str:
    return jwt.encode({"sub": email, "nome": nome, "exp": int(time.time()) + EXPIRA_S}, SEGREDO, algorithm="HS256")


def ler_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SEGREDO, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


class LimiteTentativas:
    """5 falhas em 5 minutos bloqueiam a chave (ip + e-mail) por 5 minutos. Em memoria: na AWS, WAF/Cognito."""

    def __init__(self, maximo: int = 5, janela_s: int = 300) -> None:
        self.maximo, self.janela_s, self.falhas = maximo, janela_s, {}

    def _recentes(self, chave: str) -> list[float]:
        agora = time.time()
        self.falhas[chave] = [t for t in self.falhas.get(chave, []) if agora - t < self.janela_s]
        return self.falhas[chave]

    def bloqueado(self, chave: str) -> bool:
        return len(self._recentes(chave)) >= self.maximo

    def registrar_falha(self, chave: str) -> None:
        self._recentes(chave).append(time.time())

    def limpar(self, chave: str) -> None:
        self.falhas.pop(chave, None)
