"""Test AES-128-ECB cipher."""

import os

from nanobot.channels.weixin.cdn import AesEcbCipher


def test_aes_encrypt_decrypt():
    """Test encryption and decryption."""
    key = os.urandom(16)
    plaintext = b"test data"

    ciphertext = AesEcbCipher.encrypt(key, plaintext)
    decrypted = AesEcbCipher.decrypt(key, ciphertext)

    assert plaintext == decrypted


def test_aes_encrypt_different_key():
    """Test that different key fails decryption."""
    key1 = os.urandom(16)
    key2 = os.urandom(16)
    plaintext = b"test data"

    ciphertext = AesEcbCipher.encrypt(key1, plaintext)
    with pytest.raises(Exception):  # Decryption with wrong key fails
        AesEcbCipher.decrypt(key2, ciphertext)
