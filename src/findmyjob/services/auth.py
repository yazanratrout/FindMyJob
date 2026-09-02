"""Local single-user passphrase authentication."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlmodel import Session, select

from findmyjob.models.auth import AppAuth

_hasher = PasswordHasher()
MIN_PASSPHRASE_LEN = 8


class AuthError(ValueError):
    """Invalid passphrase input."""


def _row(session: Session) -> AppAuth | None:
    return session.exec(select(AppAuth)).first()


def is_configured(session: Session) -> bool:
    return _row(session) is not None


def set_passphrase(session: Session, passphrase: str) -> None:
    if len(passphrase) < MIN_PASSPHRASE_LEN:
        raise AuthError(f"passphrase must be at least {MIN_PASSPHRASE_LEN} characters")
    hashed = _hasher.hash(passphrase)
    row = _row(session)
    if row is None:
        session.add(AppAuth(passphrase_hash=hashed))
    else:
        row.passphrase_hash = hashed
        session.add(row)
    session.flush()


def verify_passphrase(session: Session, passphrase: str) -> bool:
    row = _row(session)
    if row is None:
        return False
    try:
        _hasher.verify(row.passphrase_hash, passphrase)
    except VerifyMismatchError:
        return False
    if _hasher.check_needs_rehash(row.passphrase_hash):
        row.passphrase_hash = _hasher.hash(passphrase)
        session.add(row)
        session.flush()
    return True
