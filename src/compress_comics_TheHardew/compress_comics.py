#!/usr/bin/env python
"""compress_comics
Find all the cbz/cbr files in the current directory and subdirectories
and compress all the jpg/png/gif images inside with jpeg xl.

Output files preserve the folder structure.
Repacks cbr into cbz.
"""

import os
import errno
import subprocess
from pathlib import Path
from .text_bar import TextBar
from .comic_compressor import ComicCompressor, statistics_string
from .argument_parser import handle_flags


def glob_relative(pattern):
    """
    Recursively get a relative list of files in the current directory matching a glob pattern
    """
    cwd = Path.cwd()
    return [f.relative_to(cwd) for f in Path.cwd().rglob(pattern)]


def compress_all_comics(prog_args, enc_args, directory):
    """
    Find all cbz/cbr books in the directory and process them.
    """
    try:
        subprocess.call('cjxl', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as error:
        if error.errno == errno.ENOENT:
            print('cjxl not found. Install libjxl')
            return
        print(error)
        raise

    files = [file for file in directory.rglob('*') if file.is_file()]

    comic_books = []
    for file in files:
        if (file.suffix.lower() in ['.cbr', '.cbz'] and
                (prog_args.overwrite or prog_args.output_directory not in file.parents)
        ):
            comic_books.append(file)

    with TextBar(total=len(comic_books),
                 text='Comic books',
                 position=2,
                 unit='book',
                 colour='#ff004c') as pbar:
        original_size = 0
        compressed_size = 0
        for book in comic_books:
            original_size += os.path.getsize(book)
            compressor = ComicCompressor(book, directory, prog_args, enc_args)
            compressed_path = compressor.compress()
            compressed_size += os.path.getsize(compressed_path)
            pbar.display('', 1)  # clear position 1
            stat_string = statistics_string(compressed_size, original_size, 'Comic books')
            pbar.update(text=stat_string)

        pbar.display('', 2)
        pbar.close(filled=True)


def main():
    """
    Compress all cbz/cbr files in the current directory
    """
    prog_args, enc_args = handle_flags()
    try:
        compress_all_comics(prog_args, enc_args, Path.cwd())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
