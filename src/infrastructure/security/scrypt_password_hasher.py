"""Băm và xác thực mật khẩu sử dụng hashlib.scrypt."""

import base64
import hashlib
import hmac
import secrets

from src.application.security import PasswordHasher


class ScryptPasswordHasher(PasswordHasher):
    """Triển khai PasswordHasher bằng scrypt kèm salt ngẫu nhiên cho mỗi mật khẩu."""

    def __init__(self, n: int = 2**14, r: int = 8, p: int = 1, salt_size: int = 16, key_len: int = 64):
        self.n, self.r, self.p = n, r, p
        self.salt_size = salt_size
        self.key_len = key_len

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(self.salt_size)
        digest = self._derive(password, salt, self.n, self.r, self.p, self.key_len)
        return "$".join([
            "scrypt", str(self.n), str(self.r), str(self.p),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ])

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, n, r, p, salt_b64, digest_b64 = password_hash.split("$")
            if algorithm != "scrypt":
                return False
            expected = base64.b64decode(digest_b64)
            actual = self._derive(
                password, base64.b64decode(salt_b64), int(n), int(r), int(p), len(expected)
            )
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def _derive(password: str, salt: bytes, n: int, r: int, p: int, key_len: int) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=key_len, maxmem=64 * 1024 * 1024
        )
