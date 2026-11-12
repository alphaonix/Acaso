"""Hash de senha (scrypt, biblioteca padrao). Formato: scrypt$N$r$p$sal_hex$hash_hex. A API so verifica (app/seguranca.py)."""
import hashlib
import os


def hash_senha(senha: str, n: int = 2**14, r: int = 8, p: int = 1) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${sal.hex()}${h.hex()}"
