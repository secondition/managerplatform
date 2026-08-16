from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, settings, validate_feishu_chat_settings
from app.core.credential_crypto import (
    CredentialCipher,
    CredentialConfigurationError,
    CredentialDecryptionError,
)
from app.core.security import utcnow
from app.models.feishu_chat import FeishuUserCredential
from app.models.user import User
from app.services.feishu_user_oauth_client import (
    FeishuOAuthIdentity,
    FeishuOAuthToken,
    FeishuUserOAuthClient,
    FeishuUserOAuthError,
    missing_required_chat_scopes,
)

REFRESH_LEASE_SECONDS = 30
REFRESH_WAIT_ATTEMPTS = 3
REFRESH_WAIT_SECONDS = 0.05


class FeishuCredentialError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class CredentialStatus:
    status: str
    access_token_expires_at: datetime | None
    refresh_token_expires_at: datetime | None


class FeishuUserCredentialService:
    def __init__(
        self,
        db: Session,
        *,
        runtime_settings: Settings = settings,
        oauth_client: FeishuUserOAuthClient | None = None,
        cipher: CredentialCipher | None = None,
    ) -> None:
        self.db = db
        self.settings = runtime_settings
        self.oauth_client = oauth_client or FeishuUserOAuthClient(runtime_settings)
        self._cipher = cipher

    def ensure_runtime_available(self) -> None:
        if not self.settings.feishu_chat_enabled:
            raise FeishuCredentialError("chat_disabled")
        try:
            validate_feishu_chat_settings(self.settings)
            self._get_cipher()
        except (RuntimeError, CredentialConfigurationError) as exc:
            raise FeishuCredentialError("chat_configuration_invalid") from exc

    async def authorize_user(self, user: User, code: str) -> FeishuUserCredential:
        self.ensure_runtime_available()
        try:
            token = await self.oauth_client.exchange_authorization_code(code)
            self._require_scopes(token.scopes)
            identity = await self._resolve_identity(token, user)
            self._require_matching_identity(user, identity)
            return self._save_authorization(user, token)
        except FeishuUserOAuthError as exc:
            raise FeishuCredentialError(exc.category, retryable=not exc.permanent) from exc

    def get_status(self, user_id: int) -> CredentialStatus:
        credential = self._get_credential(user_id)
        if credential is None:
            return CredentialStatus("authorization_required", None, None)
        status = credential.status
        if status not in {"active", "refreshing", "reauthorization_required", "revoked"}:
            status = "reauthorization_required"
        return CredentialStatus(
            status,
            credential.access_token_expires_at,
            credential.refresh_token_expires_at,
        )

    async def get_valid_access_token(self, user_id: int) -> str:
        self.ensure_runtime_available()
        credential = self._require_usable_credential(user_id)
        now = utcnow()
        refresh_at = now + timedelta(
            seconds=self.settings.feishu_chat_token_refresh_skew_seconds
        )
        if (
            credential.access_token_expires_at is not None
            and credential.access_token_expires_at > refresh_at
        ):
            try:
                return self._decrypt_access_token(credential)
            except CredentialDecryptionError as exc:
                self._mark_reauthorization_required(
                    credential,
                    "credential_decryption_failed",
                )
                raise FeishuCredentialError("authorization_required") from exc

        if not self._acquire_refresh_lease(credential.id, now):
            return await self._wait_for_refresh(user_id)
        return await self._refresh_with_lease(credential.id, now)

    def disconnect(self, user: User) -> str:
        credential = self._get_credential(user.id)
        if credential is None:
            return "revoked"
        credential.access_token_encrypted = None
        credential.access_token_expires_at = None
        credential.refresh_token_encrypted = None
        credential.refresh_token_expires_at = None
        credential.granted_scopes_json = []
        credential.status = "revoked"
        credential.refresh_lease_expires_at = None
        credential.last_error = "disconnected_by_user"
        credential.updated_by = user.id
        self.db.commit()
        return credential.status

    async def _resolve_identity(
        self,
        token: FeishuOAuthToken,
        user: User,
    ) -> FeishuOAuthIdentity:
        token_identity = FeishuOAuthIdentity(
            open_id=token.open_id,
            union_id=token.union_id,
        )
        if self._has_comparable_identity(user, token_identity):
            return token_identity
        return await self.oauth_client.fetch_identity(token.access_token)

    def _save_authorization(
        self,
        user: User,
        token: FeishuOAuthToken,
    ) -> FeishuUserCredential:
        if token.refresh_token is None or token.refresh_expires_in is None:
            raise FeishuCredentialError("token_response_incomplete")
        cipher = self._get_cipher()
        access_encrypted = cipher.encrypt(token.access_token)
        refresh_encrypted = cipher.encrypt(token.refresh_token)
        now = utcnow()
        credential = self._get_credential(user.id)
        if credential is None:
            credential = FeishuUserCredential(user_id=user.id, created_by=user.id)
            self.db.add(credential)
        credential.access_token_encrypted = access_encrypted
        credential.access_token_expires_at = now + timedelta(seconds=token.access_expires_in)
        credential.refresh_token_encrypted = refresh_encrypted
        credential.refresh_token_expires_at = now + timedelta(
            seconds=token.refresh_expires_in
        )
        credential.granted_scopes_json = sorted(token.scopes)
        credential.status = "active"
        credential.refresh_lease_expires_at = None
        credential.last_refreshed_at = now
        credential.last_error = None
        credential.updated_by = user.id
        self.db.commit()
        self.db.refresh(credential)
        return credential

    def _require_usable_credential(self, user_id: int) -> FeishuUserCredential:
        credential = self._get_credential(user_id)
        if credential is None or credential.status in {"reauthorization_required", "revoked"}:
            raise FeishuCredentialError("authorization_required")
        if credential.status not in {"active", "refreshing"}:
            raise FeishuCredentialError("authorization_required")
        self._require_scopes(frozenset(credential.granted_scopes_json or []))
        return credential

    def _get_credential(self, user_id: int) -> FeishuUserCredential | None:
        return self.db.scalar(
            select(FeishuUserCredential).where(
                FeishuUserCredential.user_id == user_id,
                FeishuUserCredential.deleted_at.is_(None),
            )
        )

    def _acquire_refresh_lease(self, credential_id: int, now) -> bool:
        lease_until = now + timedelta(seconds=REFRESH_LEASE_SECONDS)
        result = self.db.execute(
            update(FeishuUserCredential)
            .where(
                FeishuUserCredential.id == credential_id,
                FeishuUserCredential.deleted_at.is_(None),
                FeishuUserCredential.status.in_(("active", "refreshing")),
                or_(
                    FeishuUserCredential.status != "refreshing",
                    FeishuUserCredential.refresh_lease_expires_at.is_(None),
                    FeishuUserCredential.refresh_lease_expires_at <= now,
                ),
            )
            .values(
                status="refreshing",
                refresh_lease_expires_at=lease_until,
                updated_at=now,
            )
        )
        self.db.commit()
        return result.rowcount == 1

    async def _wait_for_refresh(self, user_id: int) -> str:
        for _ in range(REFRESH_WAIT_ATTEMPTS):
            await asyncio.sleep(REFRESH_WAIT_SECONDS)
            self.db.expire_all()
            credential = self._require_usable_credential(user_id)
            if credential.status == "active":
                if (
                    credential.access_token_expires_at is not None
                    and credential.access_token_expires_at > utcnow()
                ):
                    return self._decrypt_access_token(credential)
                break
            if (
                credential.refresh_lease_expires_at is None
                or credential.refresh_lease_expires_at <= utcnow()
            ):
                return await self.get_valid_access_token(user_id)
        raise FeishuCredentialError("credential_refresh_in_progress", retryable=True)

    async def _refresh_with_lease(self, credential_id: int, refresh_started_at) -> str:
        self.db.expire_all()
        credential = self.db.get(FeishuUserCredential, credential_id)
        if credential is None or credential.deleted_at is not None:
            raise FeishuCredentialError("authorization_required")

        old_access_token: str | None = None
        try:
            old_access_token = self._decrypt_access_token(credential)
            if (
                credential.refresh_token_expires_at is None
                or credential.refresh_token_expires_at <= refresh_started_at
            ):
                self._mark_reauthorization_required(credential, "refresh_token_expired")
                raise FeishuCredentialError("authorization_required")
            refresh_token = self._decrypt_refresh_token(credential)
            previous_scopes = frozenset(credential.granted_scopes_json or [])
            refreshed = await self.oauth_client.refresh_access_token(
                refresh_token,
                fallback_scopes=previous_scopes,
            )
            self._require_scopes(refreshed.scopes)
            return self._save_refresh(credential, refreshed, refresh_started_at)
        except CredentialDecryptionError as exc:
            self._mark_reauthorization_required(credential, "credential_decryption_failed")
            raise FeishuCredentialError("authorization_required") from exc
        except FeishuUserOAuthError as exc:
            if exc.permanent:
                self._mark_reauthorization_required(credential, exc.category)
                raise FeishuCredentialError("authorization_required") from exc
            self._release_refresh_lease(credential, exc.category)
            if (
                old_access_token is not None
                and credential.access_token_expires_at is not None
                and credential.access_token_expires_at > utcnow()
            ):
                return old_access_token
            raise FeishuCredentialError(exc.category, retryable=True) from exc
        except FeishuCredentialError:
            if credential.status == "refreshing":
                self._mark_reauthorization_required(credential, "scope_missing")
            raise

    def _save_refresh(
        self,
        credential: FeishuUserCredential,
        token: FeishuOAuthToken,
        refreshed_at,
    ) -> str:
        cipher = self._get_cipher()
        credential.access_token_encrypted = cipher.encrypt(token.access_token)
        credential.access_token_expires_at = refreshed_at + timedelta(
            seconds=token.access_expires_in
        )
        if token.refresh_token:
            credential.refresh_token_encrypted = cipher.encrypt(token.refresh_token)
        if token.refresh_expires_in is not None:
            credential.refresh_token_expires_at = refreshed_at + timedelta(
                seconds=token.refresh_expires_in
            )
        credential.granted_scopes_json = sorted(token.scopes)
        credential.status = "active"
        credential.refresh_lease_expires_at = None
        credential.last_refreshed_at = refreshed_at
        credential.last_error = None
        self.db.commit()
        return token.access_token

    def _release_refresh_lease(
        self,
        credential: FeishuUserCredential,
        error_category: str,
    ) -> None:
        credential.status = "active"
        credential.refresh_lease_expires_at = None
        credential.last_error = error_category
        self.db.commit()

    def _mark_reauthorization_required(
        self,
        credential: FeishuUserCredential,
        reason: str,
    ) -> None:
        credential.status = "reauthorization_required"
        credential.refresh_lease_expires_at = None
        credential.last_error = reason
        self.db.commit()

    def _decrypt_access_token(self, credential: FeishuUserCredential) -> str:
        return self._get_cipher().decrypt(credential.access_token_encrypted or "")

    def _decrypt_refresh_token(self, credential: FeishuUserCredential) -> str:
        return self._get_cipher().decrypt(credential.refresh_token_encrypted or "")

    def _get_cipher(self) -> CredentialCipher:
        if self._cipher is None:
            self._cipher = CredentialCipher(self.settings.feishu_credential_encryption_key)
        return self._cipher

    def _require_scopes(self, scopes: frozenset[str]) -> None:
        missing = missing_required_chat_scopes(scopes)
        if missing:
            raise FeishuCredentialError("required_scopes_missing")

    def _has_comparable_identity(
        self,
        user: User,
        identity: FeishuOAuthIdentity,
    ) -> bool:
        return bool(
            (identity.open_id and user.feishu_open_id)
            or (identity.union_id and user.feishu_union_id)
        )

    def _require_matching_identity(
        self,
        user: User,
        identity: FeishuOAuthIdentity,
    ) -> None:
        comparisons: list[bool] = []
        if identity.open_id and user.feishu_open_id:
            comparisons.append(identity.open_id == user.feishu_open_id)
        if identity.union_id and user.feishu_union_id:
            comparisons.append(identity.union_id == user.feishu_union_id)
        if not comparisons or not all(comparisons):
            raise FeishuCredentialError("feishu_identity_mismatch")
