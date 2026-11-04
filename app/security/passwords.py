import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session


_HASH_PREFIX = "scrypt$"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 64


def is_password_hash(value: str) -> bool:
    return value.startswith(_HASH_PREFIX)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    salt = secrets.token_bytes(_SALT_BYTES)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_BYTES,
        maxmem=64 * 1024 * 1024,
    )
    return (
        f"{_HASH_PREFIX}{_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}"
        f"${salt.hex()}${derived_key.hex()}"
    )


def verify_password(password: str, stored_value: str) -> bool:
    if not is_password_hash(stored_value):
        return hmac.compare_digest(password, stored_value)

    try:
        algorithm, n, r, p, salt_hex, key_hex = stored_value.split("$")
        if (
            algorithm != "scrypt"
            or int(n) != _SCRYPT_N
            or int(r) != _SCRYPT_R
            or int(p) != _SCRYPT_P
        ):
            return False
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        if len(salt) != _SALT_BYTES or len(expected_key) != _KEY_BYTES:
            return False
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_KEY_BYTES,
            maxmem=64 * 1024 * 1024,
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual_key, expected_key)


def migrate_legacy_passwords(db: Session) -> int:
    from app.models.usuario import Usuario

    migrated = 0
    for usuario in db.query(Usuario).all():
        if not is_password_hash(usuario.password):
            usuario.password = hash_password(usuario.password)
            migrated += 1
    if migrated:
        db.commit()
    return migrated
