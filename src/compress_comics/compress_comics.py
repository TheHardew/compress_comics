#!/usr/bin/env python
"""compress_comics
Find all the cbz/cbr files in the current directory and subdirectories
and compress all the jpg/png/gif images inside with jpeg xl.

Output files preserve the folder structure.
Repacks cbr into cbz.
"""

import errno
import subprocess
from pathlib import Path
from .text_bar import TextBar
from .comic_compressor import ComicCompressor, statistics_string
from .argument_parser import handle_flags


def find_cjxl():
    local_candidates = Path('.').glob('./cjxl*')

    try:
        for binary in local_candidates:
            subprocess.call(binary, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return binary.resolve()
    except OSError:
        pass

    try:
        subprocess.call('cjxl', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Path('cjxl')
    except OSError as error:
        if error.errno == errno.ENOENT:
            print('cjxl not found. Install libjxl and put in in PATH or in the current directory')
            return
        print(error)
        raise


def find_input_files(program_args, working_directory):
    files = [file for file in working_directory.rglob('*') if file.is_file()]

    comic_books = []
    for file in files:
        if (file.suffix.lower() in ['.cbr', '.cbz'] and
                # overwrite only if input == output
                # we don't want to recompress files that were just output
                # that might happen output folder is in input, but they are not the same
                (program_args.overwrite and program_args.output_directory == Path('.').resolve()
                 or program_args.output_directory not in file.parents)
        ):
            output_directory = program_args.output_directory
            output_directory /= file.relative_to(working_directory).parent
            output_file = output_directory / file.with_suffix('.cbz').name

            if output_file.exists() and not program_args.overwrite:
                raise FileExistsError(f'File exists - {output_file}')
            comic_books.append((file, output_file))

    return comic_books


def compress_all_comics(prog_args, enc_args, directory):
    """
    Find all cbz/cbr books in the directory and process them.
    """

    cjxl_path = find_cjxl()
    comic_books = find_input_files(prog_args, directory)

    with TextBar(total=len(comic_books),
                 text='Comic books',
                 position=2,
                 unit='book',
                 colour='#ff004c') as pbar:
        original_size = 0
        compressed_size = 0
        for (book, output_book) in comic_books:
            compressor = ComicCompressor(book, output_book, enc_args, cjxl_path, prog_args.threads)
            original_size += compressor.original_size
            compressor.compress()
            compressed_size += compressor.compressed_size
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
