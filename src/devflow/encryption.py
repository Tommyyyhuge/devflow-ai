"""加密工具模块 — API Key 等敏感信息安全存储

使用 Fernet 对称加密（AES-128-CBC + HMAC）
密钥自动管理：首次使用时生成，存储在 ~/.devflow/.encryption_key
"""

from pathlib import Path

from cryptography.fernet import Fernet


def _get_or_create_key() -> bytes:
    """获取或创建加密密钥"""
    key_file = Path.home() / ".devflow" / ".encryption_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)

    if key_file.exists():
        return key_file.read_bytes()

    # 生成新密钥
    key = Fernet.generate_key()
    key_file.write_bytes(key)
    # 设置文件权限（仅当前用户可读）
    import os

    os.chmod(key_file, 0o600)
    return key


def _get_fernet() -> Fernet:
    """获取 Fernet 实例"""
    key = _get_or_create_key()
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """加密字符串值

    Args:
        value: 要加密的明文

    Returns:
        加密后的密文（Base64 编码）
    """
    if not value:
        return ""
    f = _get_fernet()
    encrypted = f.encrypt(value.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_value(encrypted_value: str) -> str:
    """解密字符串值

    Args:
        encrypted_value: 加密后的密文

    Returns:
        解密后的明文
    """
    if not encrypted_value:
        return ""
    try:
        f = _get_fernet()
        decrypted = f.decrypt(encrypted_value.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception:
        # 解密失败，可能是明文或已损坏
        return encrypted_value


def is_encrypted(value: str) -> bool:
    """检查值是否已加密

    Fernet 加密后的值通常以 'gAAAAA' 开头
    """
    if not value:
        return False
    return value.startswith("gAAAAA")
