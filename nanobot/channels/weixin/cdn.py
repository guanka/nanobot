"""Media file handling with AES-128-ECB encryption."""

import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from dataclasses import dataclass

from loguru import logger


class AesEcbCipher:
    """AES-128-ECB encryption/decryption with PKCS7 padding."""

    @staticmethod
    def encrypt(key: bytes, data: bytes) -> bytes:
        """Encrypt data with AES-128-ECB."""
        cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        return encryptor.update(padded_data) + encryptor.finalize()

    @staticmethod
    def decrypt(key: bytes, data: bytes) -> bytes:
        """Decrypt data with AES-128-ECB."""
        cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
        decryptor = cipher.decryptor()
        unpadder = padding.PKCS7(128).unpadder()
        padded_data = decryptor.update(data) + decryptor.finalize()
        return unpadder.update(padded_data) + unpadder.finalize()


@dataclass
class MediaReference:
    """CDN reference for uploaded media."""
    encrypt_query_param: str
    aes_key: str  # base64-encoded
    file_size: int
    file_size_ciphertext: int
