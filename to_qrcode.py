#!/usr/bin/env python

from __future__ import annotations

import argparse
import glob
import lzma
import os
import sys
import tarfile
import tempfile
import typing

import qrcode.constants
import qrcode.main
import qrcode.util


_qrcode_infos = {
    "L": (qrcode.constants.ERROR_CORRECT_L, 7089),
    "M": (qrcode.constants.ERROR_CORRECT_M, 5596),
    "Q": (qrcode.constants.ERROR_CORRECT_Q, 3993),
    "H": (qrcode.constants.ERROR_CORRECT_H, 3057),
}


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e",
        "--error",
        default="M",
        help="sets the error correction level of the code",
        choices=tuple(_qrcode_infos.keys()),
    )
    parser.add_argument(
        "-o",
        "--output",
        default=".",
        help="path to hold QR code folder",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="verbose output.",
    )
    parser.add_argument(
        "path",
        nargs="+",
        help="path to generate QR code",
    )
    return parser.parse_args()


class LZMAFile(typing.IO[bytes]):
    _fileobj: typing.Final[typing.IO[bytes]]
    _compressor: typing.Optional[lzma.LZMACompressor]
    _offset: int

    def __init__(self, fileobj: typing.IO[bytes]):
        self._fileobj = fileobj
        self._compressor = lzma.LZMACompressor(
            format=lzma.FORMAT_XZ,
            check=lzma.CHECK_SHA256,
        )
        self._offset = 0

    @property
    @typing.override
    def closed(self) -> bool:
        return True if self._compressor is None else self._fileobj.closed

    @typing.override
    def close(self) -> None:
        compressor = self._compressor
        if compressor is not None:
            self._fileobj.write(compressor.flush())

    @typing.override
    def readable(self) -> bool:
        return False

    @typing.override
    def seekable(self) -> bool:
        return False

    @typing.override
    def tell(self) -> int:
        return self._offset

    @typing.override
    def writable(self) -> bool:
        return True if self._compressor is None else self._fileobj.writable()

    @typing.override
    def write(self, s: bytes) -> int:
        compressor = self._compressor
        result = len(s)
        if compressor is not None:
            self._fileobj.write(compressor.compress(s))
            self._offset += result
        return result

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()


def main():
    args = parse_arguments()

    qrcode_info = _qrcode_infos[args.error]
    str_digits = qrcode_info[1]
    try:
        if sys.get_int_max_str_digits() < str_digits:
            sys.set_int_max_str_digits(str_digits)
    except AttributeError:
        pass
    max_chunk_size = int("9" * str_digits).bit_length() // 8 - 1

    with tempfile.TemporaryFile() as temp_file:
        with LZMAFile(temp_file) as lzma_file:
            # reading input files
            with tarfile.open(mode="w", fileobj=lzma_file) as archive_file:
                for path_glob in args.path:
                    for path in glob.iglob(path_glob):
                        if args.verbose:
                            print(f"adding: {path} ...", end="", flush=True)
                        archive_file.add(path)
                        if args.verbose:
                            print(f"\radding: {path} ... done")

        temp_file.seek(0, 0)

        # creating output folder
        os.makedirs(args.output, exist_ok=True)

        # generating QR code
        png_file_index = 0
        while True:
            chunk = temp_file.read(max_chunk_size)
            if not chunk:
                break

            if png_file_index >= 255:
                print("Too many image files: > 255", file=sys.stderr)
                exit(1)

            output_path = os.path.join(args.output, f"{png_file_index}.png")
            if args.verbose:
                print(f"writing: {output_path} ...", end="", flush=True)

            png_file_index += 1
            chunk_bytes = str(
                int.from_bytes(
                    bytes((png_file_index,)) + chunk,
                    "big",
                )
            ).encode()
            code = qrcode.main.QRCode(error_correction=qrcode_info[0])
            code.add_data(
                qrcode.util.QRData(
                    chunk_bytes,
                    qrcode.util.MODE_NUMBER,
                    False,
                )
            )
            code.make(True)
            image = code.make_image()
            image.save(output_path)

            if args.verbose:
                print(f"\rwriting: {output_path} ... done")


if __name__ == "__main__":
    main()
