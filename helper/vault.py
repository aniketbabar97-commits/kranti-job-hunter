"""Encrypted store for the job-portal accounts the helper creates (Workday, SuccessFactors, ...).

Passwords live only in helper/vault.enc (git-ignored), encrypted with Fernet. The Fernet key is derived
(PBKDF2-HMAC-SHA256) from VAULT_KEY in helper/me.env, so the file is useless without me.env.
Nothing here is ever printed or logged.

    from helper import vault
    acct = vault.get("myworkdayjobs.com")          # {"email": ..., "password": ...} or None
    vault.set("myworkdayjobs.com", email, pw)
    pw = vault.new_password("myworkdayjobs.com")  # ACCOUNT_PASSWORD from me.env if set, else random
"""
import base64
import json
import os
import secrets
import string
from pathlib import Path

HERE = Path(__file__).resolve().parent
VAULT = HERE / "vault.enc"
_SALT = b"kranti-job-hunter-vault-v1"  # fixed salt: the secret is VAULT_KEY, which never leaves me.env
_ITER = 390_000


def _key():
    secret = os.environ.get("VAULT_KEY", "").strip()
    if not secret:
        _load_env()
        secret = os.environ.get("VAULT_KEY", "").strip()
    if not secret:
        raise RuntimeError("VAULT_KEY missing in helper/me.env (any long random sentence works)")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=_ITER)
    return base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))


def _load_env():
    f = HERE / "me.env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(_key())


def _read():
    if not VAULT.exists():
        return {}
    from cryptography.fernet import InvalidToken
    try:
        return json.loads(_fernet().decrypt(VAULT.read_bytes()).decode("utf-8"))
    except InvalidToken:
        raise RuntimeError("helper/vault.enc cannot be decrypted: VAULT_KEY changed? (delete the file to start over)")


def _write(data):
    VAULT.write_bytes(_fernet().encrypt(json.dumps(data, sort_keys=True).encode("utf-8")))
    try:
        os.chmod(VAULT, 0o600)
    except OSError:
        pass


def site_key(site):
    """Normalise a URL / host to the account key: 'https://sap.wd3.myworkdayjobs.com/x' -> 'sap.wd3.myworkdayjobs.com'."""
    s = site.strip().lower()
    s = s.split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0]
    return s[4:] if s.startswith("www.") else s


def get(site):
    """{'email':..., 'password':...} for this site (exact host, else its parent domain), or None."""
    data = _read()
    key = site_key(site)
    parts = key.split(".")
    for i in range(len(parts) - 1):
        hit = data.get(".".join(parts[i:]))
        if hit:
            return hit
    return None


def set(site, email, password):  # noqa: A001 - mirrors a dict API on purpose
    data = _read()
    data[site_key(site)] = {"email": email, "password": password}
    _write(data)


def delete(site):
    data = _read()
    if data.pop(site_key(site), None) is not None:
        _write(data)
        return True
    return False


def sites():
    return sorted(_read())


def new_password(site=None, length=16):
    """ACCOUNT_PASSWORD from me.env when set (one password she knows), else a random one that satisfies the
    usual portal rules (upper, lower, digit, symbol, >= 12 chars)."""
    _load_env()
    fixed = os.environ.get("ACCOUNT_PASSWORD", "").strip()
    if fixed:
        return fixed
    alphabet = string.ascii_letters + string.digits + "!@#$%&*?"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw) and any(c in "!@#$%&*?" for c in pw)):
            return pw
