#!/usr/bin/env python
"""compress_comics
Find all the cbz/cbr files in the current directory and subdirectories
and compress all the jpg/png/gif images inside with jpeg xl.

Output files preserve the folder structure.
Repacks cbr into cbz.
"""

import os
import sys
import errno
import subprocess
from pathlib import Path
import multiprocessing as mp
from argparse import ArgumentParser, Namespace
from .text_bar import TextBar
from .comic_compressor import ComicCompressor, statistics_string


def glob_relative(pattern):
    """
    Recursively get a relative list of files in the current directory matching a glob pattern
    """
    cwd = Path.cwd()
    return [f.relative_to(cwd) for f in Path.cwd().rglob(pattern)]


def parse_args(add_help=True):
    parser = ArgumentParser(add_help=add_help)

    program_group = parser.add_argument_group('program options', 'Options influencing program behaviour')
    program_group.add_argument('-t', '--threads', type=int, default=mp.cpu_count(),
                               help='The number of images to compress at once. Defaults to cpu threads.')
    program_group.add_argument('-O', '--overwrite-destination', action='store_true',
                               help='Overwrite the destination, if it exists. Default: False')

    output_group = program_group.add_mutually_exclusive_group(required=True)
    output_group.add_argument('output_directory', type=str, help='Output directory', nargs='?')
    output_group.add_argument('-o', '--overwrite', action='store_true',
                              help='Overwrite the original file. Default: False. '
                                   'Can only be passed if outputting to a folder')

    if not add_help:
        program_args = vars(parser.parse_known_args()[0])

    encoder_group = parser.add_argument_group('cjxl options', 'Options passed to the cjxl encoder')
    encoder_group.add_argument('-e', '--effort', type=int, choices=range(1, 10),
                               help='Encoder effort setting.')
    encoder_group.add_argument('-E', '--modular_nb_prev_channels', type=int,
                               help='[modular encoding] number of extra MA tree properties to use.')
    encoder_group.add_argument('--brotli_effort', type=int, choices=range(1, 12),
                               help='Brotli effort setting.')
    encoder_group.add_argument('-j', '--lossless_jpeg', type=int, default=1, choices=range(0, 2),
                               help='If the input is JPEG, losslessly transcode JPEG, rather than using '
                                    'reencoded pixels. 0 - Rencode, 1 - lossless. Default: 1.')
    encoder_group.add_argument('-m', '--modular', type=int, choices=range(0, 2),
                               help='Use modular mode (0 = enforce VarDCT, 1 = enforce modular mode).')
    encoder_group.add_argument('--num_threads', type=int, default=None,
                               help='Number of threads to use to compress one image. '
                                    'Default: (cpu threads) / --threads')

    quality_group = encoder_group.add_mutually_exclusive_group()
    quality_group.add_argument('-d', '--distance', type=int, default=0,
                               help='Max. butteraugli distance, lower = higher quality.  Default: 0.')
    quality_group.add_argument('-q', '--quality', type=float,
                               help='Quality setting, higher value = higher quality. This is internally mapped to --distance.'
                                    '\n100 = mathematically lossless. 90 = visually lossless.'
                                    '\nQuality values roughly match libjpeg quality.'
                                    '\nRecommended range: 68 .. 96. Allowed range: 0 .. 100. Mutually exclusive with --distance.')

    if not add_help:
        encoder_args = {k: v for k, v in vars(parser.parse_known_args()[0]).items() if k not in program_args}

        program_args = Namespace(**program_args)
        encoder_args = Namespace(**encoder_args)

        if encoder_args.num_threads is None:
            encoder_args.num_threads = mp.cpu_count() // program_args.threads

        return program_args, encoder_args

    parser.parse_args()


def handle_flags():
    """
    Process command line arguments
    :return: the dictionary of processed arguments
    """

    # an ugly trick to be able to split arguments into multiple groups and still
    # have auto help generation
    # if the help flag is detected, the program will abort from argparse
    # if not, the flags will be parsed twice
    argv_copy = sys.argv
    parse_args(add_help=True)

    sys.argv = argv_copy
    program_args, encoder_args = parse_args(add_help=False)

    if program_args.overwrite_destination and not program_args.output_directory:
        raise ValueError('Overwrite destination can only be used when outputting to a folder.')

    if not program_args.overwrite:
        program_args.output_directory = Path(program_args.output_directory).as_posix()

    return program_args, encoder_args


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
                (prog_args.overwrite or Path(prog_args.output_directory) not in file.parents)
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
