from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class CredentialConfigurationError(RuntimeError):
    pass


class CredentialDecryptionError(RuntimeError):
    pass


class CredentialCipher:
    def __init__(self, encryption_key: str) -> None:
        normalized_key = encryption_key.strip()
        if not normalized_key:
            raise CredentialConfigurationError("Credential encryption is not configured")
        try:
            self._fernet = Fernet(normalized_key.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as exc:
            raise CredentialConfigurationError(
                "Credential encryption configuration is invalid"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise CredentialConfigurationError("Credential value is empty")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            raise CredentialDecryptionError("Stored credential is unavailable")
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
            raise CredentialDecryptionError("Stored credential cannot be decrypted") from exc
