#!/usr/bin/python3
# encoding: utf-8

from base64 import a85encode
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.base import Cipher
from cryptography.hazmat.primitives.ciphers.modes import CTR
from cryptography.hazmat.primitives.padding import PKCS7
from getpass import getpass
from hashlib import sha256
from lzma import CHECK_SHA256, LZMACompressor
from sys import argv, stdout


def get_digest(password):
    hash = sha256()
    hash.update(password.encode('utf-8'))
    return hash.digest()


def encode_write_block(data):
    if len(data) >= 4:
        i = len(data) & ~0x3
        stdout.buffer.write(a85encode(data[:i]))
        data = data[i:]
    return data


def main():
    password = getpass('Password: ')

    for i in range(1, len(argv)):
        path = argv[i]

        digest = get_digest(password)
        iv_size = AES.block_size // 8
        encryptor = Cipher(
            AES(digest),
            CTR(
                digest * (iv_size // len(digest)) +
                digest[:iv_size % len(digest)]
            ),
            backend=backend
        ).encryptor()
        padder = PKCS7(AES.block_size).padder()
        compressor = LZMACompressor(check=CHECK_SHA256, preset=9)
        data = b''
        stdout.buffer.write(b'<~')
        with open(path, 'rb') as in_file:
            while True:
                chunk = in_file.read(0x1000)
                if not chunk:
                    break
                data = encode_write_block(
                    data +
                    encryptor.update(
                        padder.update(compressor.compress(chunk))
                    )
                )
        data = encode_write_block(
            data +
            encryptor.update(padder.update(compressor.flush()))
        )
        data = encode_write_block(
            data +
            encryptor.update(padder.finalize())
        )
        stdout.buffer.write(a85encode(data + encryptor.finalize()))
        stdout.buffer.write(b'~>\r\n')


if __name__ == '__main__':
    main()
