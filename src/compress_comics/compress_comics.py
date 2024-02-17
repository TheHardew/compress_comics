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


def get_output_name(input_file, working_directory, program_args):
    output_directory = program_args.output_directory
    output_directory /= input_file.relative_to(working_directory).parent
    output_file = output_directory / input_file.with_suffix('.cbz').name

    if output_file.exists() and not program_args.overwrite:
        raise FileExistsError(f'File exists - {output_file}')

    return output_file


def find_input_files(program_args, working_directory):
    comic_books = []
    outputs = set()

    for input_path in program_args.INPUT:
        comic_book = Path()
        output_file = Path()

        if input_path.is_file():
            output_file = get_output_name(input_path, working_directory, program_args)
            outputs.add(output_file)
            comic_books.append((input_path, output_file))
        else:
            files = input_path.rglob('*.*')
            files = sorted(files, key=lambda x: len(x.parents))
            for file in files:
                if (file.is_file() and file.suffix.lower() in ['.cbr', '.cbz'] and
                        file not in outputs and
                        (program_args.overwrite or program_args.output_directory not in file.parents)):
                    output_file = get_output_name(file, working_directory, program_args)

                    if output_file.exists() and not program_args.overwrite:
                        raise FileExistsError(f'File exists - {output_file}')

                    outputs.add(output_file)
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
            if (prog_args.overwrite and book.suffix.lower() != '.cbz' and book.is_file() and
                    book.parent == output_book.parent):
                book.unlink()
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
