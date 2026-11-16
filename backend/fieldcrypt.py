"""应用层字段加密。

- EncText / EncJSON：Fernet（AES-128-CBC + HMAC-SHA256），每次加密结果不同，用于链接、帖子作者与正文等。
- DetText：AES-SIV 确定性加密，同一明文得到同一密文，因此仍可做等值查询、唯一约束与主键（shop_key、domain、推广账号名）。
- 密钥来自环境变量 FIELD_ENCRYPTION_KEY（Fernet 密钥；可用逗号分隔多个，第一个用于加密，其余仅用于解密以便轮换）。
- 读取时遇到没有前缀的旧明文会原样返回，所以迁移前后应用都能工作；`python -m backend.cli encrypt-existing` 负责把旧明文加密。
- 没设置密钥时不加密（仅限开发），读取已加密的数据会明确报错。
"""
from __future__ import annotations
import base64
import json
import logging
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

log = logging.getLogger("aishops.crypt")
P_RAND = "enc1:"
P_DET = "encd:"
_state: dict = {}


def _load():
    if _state:
        return _state
    raw = [k.strip() for k in os.environ.get("FIELD_ENCRYPTION_KEY", "").split(",") if k.strip()]
    if not raw:
        log.warning("未设置 FIELD_ENCRYPTION_KEY：敏感字段将以明文保存（仅限开发环境）")
        _state.update(enabled=False)
        return _state
    fernets = [Fernet(k.encode()) for k in raw]
    first = base64.urlsafe_b64decode(raw[0] + "=" * (-len(raw[0]) % 4))
    siv_key = HKDF(hashes.SHA256(), 64, salt=None, info=b"aishops-field-siv").derive(first)
    _state.update(enabled=True, fernet=MultiFernet(fernets), siv=AESSIV(siv_key))
    return _state


def enabled() -> bool:
    return _load()["enabled"]


def _need():
    st = _load()
    if not st["enabled"]:
        raise RuntimeError("数据库里有加密字段，但没有设置 FIELD_ENCRYPTION_KEY")
    return st


def enc(s: str | None) -> str | None:
    if s is None or s == "" or not enabled():
        return s
    if s.startswith((P_RAND, P_DET)):
        return s
    return P_RAND + _load()["fernet"].encrypt(s.encode()).decode()


def dec(s):
    if not isinstance(s, str) or not s.startswith(P_RAND):
        return s
    try:
        return _need()["fernet"].decrypt(s[len(P_RAND):].encode()).decode()
    except InvalidToken:
        raise RuntimeError("字段解密失败：FIELD_ENCRYPTION_KEY 与加密时使用的不一致")


def enc_det(s: str | None) -> str | None:
    if s is None or s == "" or not enabled():
        return s
    if s.startswith((P_RAND, P_DET)):
        return s
    return P_DET + base64.urlsafe_b64encode(_load()["siv"].encrypt(s.encode(), [b"aishops"])).decode()


def dec_det(s):
    if not isinstance(s, str) or not s.startswith(P_DET):
        return s
    try:
        return _need()["siv"].decrypt(base64.urlsafe_b64decode(s[len(P_DET):].encode()), [b"aishops"]).decode()
    except Exception:
        raise RuntimeError("字段解密失败：FIELD_ENCRYPTION_KEY 与加密时使用的不一致")


class EncText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return enc(value)

    def process_result_value(self, value, dialect):
        return dec(value)


class DetText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return enc_det(value)

    def process_result_value(self, value, dialect):
        return dec_det(value)


class EncJSON(TypeDecorator):
    """JSON 值序列化后加密，存为文本。读取时兼容旧的 JSON/JSONB 明文。"""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return enc(json.dumps(value, ensure_ascii=False))

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, (list, dict)):
            return value
        value = dec(value)
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value


def generate_key() -> str:
    return Fernet.generate_key().decode()
