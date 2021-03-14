#!/usr/bin/python3
# encoding: utf-8

from base64 import a85decode
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.base import Cipher
from cryptography.hazmat.primitives.ciphers.modes import CTR
from cryptography.hazmat.primitives.padding import PKCS7
from getpass import getpass
from hashlib import sha256
from lzma import LZMADecompressor
from sys import stdin


def get_digest(password):
    hash = sha256()
    hash.update(password.encode('utf-8'))
    return hash.digest()


def main():
    password = getpass('Password: ')

    # reading all data
    digest = get_digest(password)
    iv_size = AES.block_size // 8
    for i, line in enumerate(stdin.buffer):
        with open('%d.bin' % i, 'wb+') as out_fp:
            decryptor = Cipher(
                AES(digest),
                CTR(
                    digest * (iv_size // len(digest)) +
                    digest[:iv_size % len(digest)]
                ),
                backend=backend
            ).decryptor()
            unpadder = PKCS7(AES.block_size).unpadder()
            decompressor = LZMADecompressor()

            out_fp.write(
                decompressor.decompress(
                    unpadder.update(
                        decryptor.update(
                            a85decode(line.rstrip(b'\r\n'), adobe=True)
                        )
                    )
                )
            )
            out_fp.write(
                decompressor.decompress(
                    unpadder.update(decryptor.finalize())
                )
            )
            out_fp.write(
                decompressor.decompress(unpadder.finalize())
            )


if __name__ == '__main__':
    main()
