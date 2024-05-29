#!/usr/bin/env python

from __future__ import annotations

import argparse
import lzma
import os
import sys
import tarfile
import tempfile


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        default=".",
        help="path to extracted directory",
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
        "path",
        nargs="+",
        help="directory to read QR code files",
    )
    return parser.parse_args()


_no_digits = bytes(
    filter(
        lambda v: v not in range(ord("0"), ord("9") + 1),
        range(256),
    )
)


def process_folder(input_dir: str, output_dir: str, verbose: bool) -> int:
    chunk_dict: dict[int, bytes] = {}

    for _path in os.listdir(input_dir):
        path = os.path.join(input_dir, _path)
        if os.path.isfile(path):
            if verbose:
                print(f"opening: {path} ...", end="", flush=True)
            try:
                with open(path, "rb") as file:
                    digits = file.read().translate(None, _no_digits)
            except Exception as exc_value:
                if verbose:
                    print(f"\ropening: {path} ... skipped. {exc_value}")
                continue

            try:
                i = int(digits)
                data = i.to_bytes((i.bit_length() + 7) // 8)
            except ValueError as exc_value:
                if verbose:
                    print(f"\ropening: {path} ... skipped. {exc_value}")
                continue

            if len(data) > 0:
                chunk_dict[data[0]] = data[1:]

            if verbose:
                print(f"\ropening: {path} ... done.")

    # checking chunk dictionary
    absent_index_set = set(chunk_dict.keys())
    absent_index_set.difference_update(range(1, len(chunk_dict) + 1))
    if absent_index_set:
        print(
            f"Need QR image: indexes={list(sorted(absent_index_set))}",
            file=sys.stderr,
        )
        return 1

    # reading list
    with tempfile.TemporaryFile() as temp_file:
        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
        for index in range(1, len(chunk_dict) + 1):
            temp_file.write(decompressor.decompress(chunk_dict[index]))

        temp_file.seek(0, 0)

        dir_tarinfo_list = []
        with tarfile.open(mode="r:", fileobj=temp_file) as archive_file:
            for tarinfo in archive_file:
                if tarinfo.isdir():
                    dir_tarinfo_list.append(tarinfo)
                if verbose:
                    print(
                        f"extracting: {tarinfo.name} ...",
                        end="",
                        flush=True,
                    )

                archive_file.extract(tarinfo, output_dir)

                if verbose:
                    print(f"\rextracting: {tarinfo.name} ... done")

        # Reverse sort directories.
        dir_tarinfo_list.sort(key=lambda a: a.name, reverse=True)

        # Set correct owner, mtime and filemode on directories.
        for tarinfo in dir_tarinfo_list:
            dirpath = os.path.join(output_dir, tarinfo.name)
            try:
                temp_file.chown(tarinfo, dirpath)
                temp_file.utime(tarinfo, dirpath)
                temp_file.chmod(tarinfo, dirpath)
            except tarfile.ExtractError:
                pass

    return 0


def main():
    args = parse_arguments()

    result = 0
    for input_dir in args.path:
        result = process_folder(input_dir, args.output_dir, args.verbose)
        if result != 0:
            break
    exit(result)


if __name__ == "__main__":
    main()
