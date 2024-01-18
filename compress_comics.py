#!/usr/bin/env python
"""compress_comics
Find all the cbz/cbr files in the current directory and subdirectories
and compress all the jpg/png/gif images inside with jpeg xl.

Output files preserve the folder structure.
Repacks cbr into cbz.
"""

import os
from shutil import copy, move
import subprocess
from pathlib import Path
from multiprocessing import Pool, cpu_count
from functools import partial
from tempfile import TemporaryDirectory, NamedTemporaryFile
import sys
import zipfile
from argparse import ArgumentParser, Namespace
from patoolib import extract_archive


def error_exit(msg, code):
    """
    Print an error message and exit with a code
    """
    print('Error:', msg, file=sys.stderr)
    sys.exit(code)


def glob_relative(pattern):
    """
    Recursively get a relative list of files in the current directory matching a glob pattern
    """
    cwd = Path.cwd()
    return [f.relative_to(cwd) for f in Path.cwd().rglob(pattern)]


def unpack(file, directory):
    """
    Unpack a comic book to a directory
    """
    extract_archive(str(file), verbosity=-1, outdir=str(directory))


def clean_tmp_dir(tmp_dir):
    """
    Remove useless files in the comic book.
    Removes Thumbs.db files and checksum (.sfv) files.
    :param tmp_dir: the directory to clean.
    """
    for file in tmp_dir.glob('*.sfv'):
        file.unlink()
    for file in tmp_dir.glob('Thumbs.db'):
        file.unlink()


def check_file_types(tmp_dir):
    """
    Make sure that all the files left in the comic book can be handled by the program.
    If there are files left that the program is not sure how to handle, stop processing the book.
    :param tmp_dir: the processed directory to check
    """
    extensions = ['.gif', '.jpg', '.jpeg', '.png', '.jxl', '.xml', '.txt']
    files = [f for f in tmp_dir.glob('**/*') if f.is_file() and f.suffix.lower() not in extensions]

    extension_string = '/'.join([ext[1:] for ext in extensions])
    if len(files):
        print(f'Some files are not {extension_string}:')
        for file in files:
            print(file)

        error_exit(f'Some files are not {extension_string}', 1)


def check_transcoding(tmp_dir):
    """
    Check that the input and output directories have the same number of files.
    If not, some files where not processed.
    :param tmp_dir: the processed directory to check.
    """
    source_files = len([file for file in Path.cwd().glob('**/*') if file.is_file()])
    jxl_files = len([file for file in tmp_dir.glob('**/*') if file.is_file()])
    if source_files != jxl_files:
        error_exit('Not all files transcoded', 2)


def handle_flags():
    """
    Process command line arguments
    :return: the dictionary of processed arguments
    """
    parser = ArgumentParser()

    parser.add_argument('-e', '--effort', type=int, default=9,
                        help='Encoder effort setting. Range: 1 .. 9. Default 9.')
    parser.add_argument('-E', '--modular_nb_prev_channels', type=int, default=3,
                        help='[modular encoding] number of extra MA tree properties to use.'
                             'Default 3.')
    parser.add_argument('--brotli_effort', type=int, default=11,
                        help='Brotli effort setting. Range: 0 .. 11. Default 11.')
    parser.add_argument('-d', '--distance', type=int, default=0,
                        help='Max. butteraugli distance, lower = higher quality.  Default 0.')
    parser.add_argument('-j', '--lossless_jpeg', type=int, default=1,
                        help='If the input is JPEG, losslessly transcode JPEG, rather than using'
                             'reencoded pixels. 0 - Rencode, 1 - lossless. Default 1.')
    parser.add_argument('-m', '--modular', type=int,
                        help='Use modular mode (not provided = encoder chooses, 0 = enforce VarDCT'
                        ', 1 = enforce modular mode).')
    parser.add_argument('-t', '--threads', type=int, default=cpu_count(),
                        help='The number of images to compress at once. Defaults to cpu threads.')
    parser.add_argument('--num_threads', type=int,
                        help='Number of threads to use to compress one image.'
                        'Defaults to (cpu threads) / --threads')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('output_directory', type=str, help='Output directory', nargs='?')
    group.add_argument('-o', '--overwrite', action='store_true',
                        help='Overwrite the original file. Defaults to False.')

    args = parser.parse_args()

    # even if it's already relative, strips things like './' from the beginning
    cwd = Path.cwd()

    if not args.overwrite:
        args.output_directory = Path(args.output_directory).resolve().relative_to(cwd)

    if not args.num_threads:
        args.num_threads = cpu_count() // args.threads

    return args


def pack(args, input_file, working_directory, processed_tmp):
    """
    Save the processed comic book, either to the output directory, or to a new temporary
    file and then overwrite the original. This way no data will be lost if we there is no space
    left on the device
    :param args: the program arguments
    :param input_file: the original file to derive the name
    :param woking_directory: program working_directory
    :param processed_tmp: the processed files
    """
    directory = working_directory
    if args.overwrite:
        directory /= input_file.parent
        try:
            with NamedTemporaryFile(dir=directory, prefix='.' + input_file.name) as tmp:
                create_comic_archive(tmp.name, processed_tmp)
                move(tmp.name, working_directory / input_file)
        except FileNotFoundError:
            # file was moved so nothing to clean up
            pass
    else:
        directory /= args.output_directory
        os.makedirs(directory / input_file.parent, exist_ok=True)
        name = directory / input_file
        name = name.with_suffix('.cbz')
        create_comic_archive(name, processed_tmp)


def compress_comic(input_file, args):
    """
    Compress a comic book
    :param input_file: the comic book to compress
    :param args: compression arguments
    """
    base = Path.cwd().resolve()

    with (
        TemporaryDirectory() as original_tmp,
        TemporaryDirectory() as processed_tmp
    ):
        original_tmp = Path(original_tmp)
        processed_tmp = Path(processed_tmp)
        unpack(input_file, original_tmp)
        clean_tmp_dir(original_tmp)
        check_file_types(original_tmp)

        os.chdir(original_tmp)
        transcode(processed_tmp, args)
        copy_files(processed_tmp)

        # shouldn't be necessary because the program checks the exit status
        check_transcoding(processed_tmp)
        pack(args, input_file, base, processed_tmp)

    os.chdir(base)


def copy_files(processed_dir):
    """
    Copy some files from the original comic book without changing them
    :param processed_dir: the directory to copy to
    """
    extensions = ['.txt', '.xml', '.jxl']
    files = [file for file in glob_relative('*') if file.suffix.lower() in extensions]
    for file in files:
        copy(file, processed_dir)


def stringify_arguments(args):
    """
    Changes all the arguments inside argparse.Namespace into strings
    """
    return Namespace(**{k: str(v) for k, v in vars(args).items()})


def transcode_file(input_file, tmp_dir, args):
    """
    Compress a single image file
    :param input_file: the file to compress
    :param tmp_dir: the directory to compress it to
    :param args: the compression arguments to pass to cjxl
    """
    output_file = tmp_dir / input_file
    output_file = output_file.with_suffix('.jxl')
    subprocess.run([
        'cjxl',
        '--brotli_effort',
        args.brotli_effort,
        '-d',
        args.distance,
        '-e',
        args.effort,
        '-E',
        args.modular_nb_prev_channels,
        '--num_threads',
        args.num_threads,
        '-j',
        args.lossless_jpeg,
        input_file,
        str(output_file),
    ],
        check=True
    )


def error_handler(pool, err):
    """
    Error handler for the other processes.
    Stops the processing early in case of a transcoding error
    :param pool: the multiprocessing pool to terminate
    :param err: the error message
    """
    print(err)
    pool.terminate()


def transcode(tmp_dir, args):
    """
    Compress all the image files in the current directory
    :param tmp_dir: the directory to compress it to
    :param args: compression arguments to pass to cjxl
    """
    for directory in glob_relative('*/'):
        os.makedirs(tmp_dir / directory, exist_ok=True)

    extensions = ['.gif', '.jpg', '.jpeg', '.png']
    files = [f for f in glob_relative('*') if f.suffix.lower() in extensions and f.is_file()]
    with Pool(args.threads) as pool:
        args = stringify_arguments(args)
        handler = partial(error_handler, pool)
        # avoid using map_async to allow the transcoding to fail early on non 0 exit status
        for file in files:
            pool.apply_async(transcode_file, args=(file, tmp_dir, args,), error_callback=handler)
        pool.close()
        pool.join()


def create_comic_archive(output_file, processed_tmp):
    """
    Pack a directory to a comic book
    :param output_file: the file to compress the comic book to
    :param processed_tmp: the directory of the files to compress
    """
    os.chdir(processed_tmp)

    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_STORED) as zipf:
        for file in glob_relative('*'):
            zipf.write(file)


def main():
    """
    Find all cbz/cbr books in the current directory and process them.
    """
    args = handle_flags()
    for comic in glob_relative('*'):
        if (comic.is_file() and
                comic.suffix in ['.cbz', '.cbr'] and
                args.output_directory not in comic.parents):
            compress_comic(comic, args)


if __name__ == "__main__":
    main()
