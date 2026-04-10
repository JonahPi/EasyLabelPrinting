import secrets


class KeyManager:
    def __init__(self):
        self._key: str = ""
        self.rotate()

    def rotate(self) -> str:
        """Generate a new cryptographically random key (12 hex chars, 48-bit entropy)."""
        self._key = secrets.token_hex(6)
        return self._key

    @property
    def current_key(self) -> str:
        return self._key

    def validate(self, candidate: str) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        return secrets.compare_digest(self._key, candidate)
