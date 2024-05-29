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
    "L": (
        qrcode.constants.ERROR_CORRECT_L,
        (
            0,
            41,
            77,
            127,
            187,
            255,
            322,
            370,
            461,
            552,
            652,
            772,
            883,
            1022,
            1101,
            1250,
            1408,
            1548,
            1725,
            1903,
            2061,
            2232,
            2409,
            2620,
            2812,
            3057,
            3514,
            3669,
            3909,
            4158,
            4417,
            4686,
            4965,
            5253,
            5529,
            5836,
            6153,
            6479,
            6743,
            7089,
        ),
    ),
    "M": (
        qrcode.constants.ERROR_CORRECT_M,
        (
            0,
            34,
            63,
            101,
            149,
            202,
            255,
            293,
            365,
            432,
            513,
            604,
            691,
            796,
            871,
            991,
            1082,
            1212,
            1346,
            1500,
            1600,
            1708,
            1872,
            2059,
            2188,
            2395,
            2544,
            2701,
            2857,
            3035,
            3289,
            3486,
            3693,
            3909,
            4134,
            4343,
            4588,
            4775,
            5039,
            5313,
            5596,
        ),
    ),
    "Q": (
        qrcode.constants.ERROR_CORRECT_Q,
        (
            0,
            27,
            48,
            77,
            111,
            144,
            178,
            207,
            259,
            312,
            364,
            427,
            489,
            580,
            621,
            703,
            775,
            876,
            948,
            1063,
            1159,
            1224,
            1358,
            1468,
            1588,
            1718,
            1804,
            1933,
            2085,
            2181,
            2358,
            2473,
            2670,
            2805,
            2949,
            3081,
            3244,
            3417,
            3599,
            3791,
            3993,
        ),
    ),
    "H": (
        qrcode.constants.ERROR_CORRECT_H,
        (
            0,
            17,
            34,
            58,
            82,
            106,
            139,
            154,
            202,
            235,
            288,
            331,
            374,
            427,
            468,
            530,
            602,
            674,
            746,
            813,
            919,
            969,
            1056,
            1108,
            1228,
            1286,
            1425,
            1501,
            1581,
            1677,
            1782,
            1897,
            2022,
            2157,
            2301,
            2361,
            2524,
            2625,
            2735,
            2927,
            3057,
        ),
    ),
}


class VersionAction(argparse.Action):
    def __init__(self, *args, default=None, type=None, nargs=None, **kwargs):
        super().__init__(*args, default=40, nargs="?", **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, str):
            try:
                i = int(values)
            except ValueError:
                raise argparse.ArgumentError(
                    self,
                    f"invalid int value: {values!r}",
                )
            if i < 1:
                raise argparse.ArgumentError(
                    self, f"{i!r} is not between 1 and 40"
                )
            if i > 40:
                raise argparse.ArgumentError(
                    self, f"{i!r} is not between 1 and 40"
                )
            setattr(namespace, self.dest, i)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e",
        "--error",
        dest="error",
        default="M",
        help="sets the error correction level of the code",
        choices=tuple(_qrcode_infos.keys()),
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        default=".",
        help="path to hold QR code folder",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        default=False,
        help="verbose output.",
    )
    parser.add_argument(
        "--max-version",
        action=VersionAction,
        dest="max_version",
        help="maximum version.",
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
    max_str_digits = qrcode_info[1][args.max_version]
    try:
        max_str_digits = min(max_str_digits, sys.get_int_max_str_digits())
    except AttributeError:
        pass
    max_chunk_size = int("9" * max_str_digits).bit_length() // 8 - 1

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
        os.makedirs(args.output_dir, exist_ok=True)

        # generating QR code
        file_index = 0
        while True:
            chunk = temp_file.read(max_chunk_size)
            if not chunk:
                break

            if file_index >= 255:
                print("Too many image files: > 255", file=sys.stderr)
                exit(1)

            output_path = os.path.join(
                args.output_dir,
                f"{file_index}.png",
            )
            if args.verbose:
                print(f"writing: {output_path} ...", end="", flush=True)

            file_index += 1
            chunk_bytes = str(
                int.from_bytes(bytes((file_index,)) + chunk)
            ).encode()
            code = qrcode.main.QRCode(
                error_correction=qrcode_info[0],
                box_size=2,
                border=8,
            )
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
