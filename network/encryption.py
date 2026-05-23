"""End-to-end encryption helpers for Ma:Vi."""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass(frozen=True)
class EncryptedPayload:
    """AES-GCM encrypted payload encoded for JSON transport."""

    encrypted: str
    nonce: str
    tag: str


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def generate_keypair() -> dict[str, str]:
    """Generate X25519 and Ed25519 key pairs as base64 strings."""
    x_private = x25519.X25519PrivateKey.generate()
    x_public = x_private.public_key()
    sign_private = ed25519.Ed25519PrivateKey.generate()
    sign_public = sign_private.public_key()
    return {
        "private_key": _b64(x_private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())),
        "public_key": _b64(x_public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)),
        "signing_private_key": _b64(sign_private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())),
        "signing_public_key": _b64(sign_public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)),
    }


def compute_shared_secret(private_key: str, public_key: str) -> bytes:
    """Compute a Diffie-Hellman shared secret with X25519."""
    private = x25519.X25519PrivateKey.from_private_bytes(_unb64(private_key))
    public = x25519.X25519PublicKey.from_public_bytes(_unb64(public_key))
    return private.exchange(public)


def derive_aes_key(shared_secret: bytes, salt: bytes | None = None) -> bytes:
    """Derive a 256-bit AES key from a shared secret."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"mavi-e2e-v1").derive(shared_secret)


def encrypt_message(plaintext: str, aes_key: bytes) -> EncryptedPayload:
    """Encrypt text with AES-256-GCM."""
    nonce = os.urandom(12)
    ciphertext_and_tag = AESGCM(aes_key).encrypt(nonce, plaintext.encode("utf-8"), None)
    ciphertext, tag = ciphertext_and_tag[:-16], ciphertext_and_tag[-16:]
    return EncryptedPayload(encrypted=_b64(ciphertext), nonce=_b64(nonce), tag=_b64(tag))


def decrypt_message(ciphertext: str, nonce: str, tag: str, aes_key: bytes) -> str:
    """Decrypt an AES-256-GCM text payload."""
    plaintext = AESGCM(aes_key).decrypt(_unb64(nonce), _unb64(ciphertext) + _unb64(tag), None)
    return plaintext.decode("utf-8")


def encrypt_file(source: Path, target: Path, aes_key: bytes) -> EncryptedPayload:
    """Encrypt a file with AES-256-GCM and write the encrypted bytes."""
    nonce = os.urandom(12)
    encrypted = AESGCM(aes_key).encrypt(nonce, source.read_bytes(), None)
    ciphertext, tag = encrypted[:-16], encrypted[-16:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(ciphertext)
    return EncryptedPayload(encrypted=str(target), nonce=_b64(nonce), tag=_b64(tag))


def decrypt_file(source: Path, target: Path, nonce: str, tag: str, aes_key: bytes) -> Path:
    """Decrypt a file written by encrypt_file."""
    plaintext = AESGCM(aes_key).decrypt(_unb64(nonce), source.read_bytes() + _unb64(tag), None)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plaintext)
    return target


def encrypt_private_key(private_key: str, password: str) -> str:
    """Encrypt a private key using a password-derived AES key."""
    salt = os.urandom(16)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000).derive(password.encode("utf-8"))
    payload = encrypt_message(private_key, key)
    return ".".join((_b64(salt), payload.nonce, payload.encrypted, payload.tag))


def decrypt_private_key(encrypted_key: str, password: str) -> str:
    """Decrypt a private key protected by encrypt_private_key."""
    salt_b64, nonce, encrypted, tag = encrypted_key.split(".", 3)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_unb64(salt_b64), iterations=390000).derive(password.encode("utf-8"))
    return decrypt_message(encrypted, nonce, tag, key)


def get_key_fingerprint(public_key: str) -> str:
    """Return a readable SHA-256 fingerprint for a public key."""
    digest = hashlib.sha256(_unb64(public_key)).hexdigest().upper()
    return " ".join(digest[i : i + 4] for i in range(0, len(digest), 4))
