#!/usr/bin/env python
"""compress_comics
Find all the cbz/cbr files in the current directory and subdirectories
and compress all the jpg/png/gif images inside with jpeg xl.

Output files preserve the folder structure.
Repacks cbr into cbz.
"""

import os
import errno
from shutil import move
import subprocess
from pathlib import Path
import multiprocessing as mp
from tempfile import TemporaryDirectory, NamedTemporaryFile
import zipfile
from argparse import ArgumentParser, Namespace
from patoolib import extract_archive
from .text_bar import TextBar
from time import sleep


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


def check_transcoding(output_file):
    """
    Make sure that all the files left in the comic book can be handled by the program.
    If there are files left that the program is not sure how to handle, stop processing the book.
    :param tmp_dir: the processed directory to check
    """
    transcoded_extensions = ['.jpg', '.jpeg', '.png', '.gif']

    with zipfile.ZipFile(output_file, 'r') as zipf:
        for file in glob_relative('*'):
            if file.is_file() and file.suffix.lower() in transcoded_extensions:
                file = file.with_suffix('.jxl')

            if file.is_file() and file.as_posix() not in zipf.namelist():
                raise RuntimeError(f'Some files were not copied {file}')


def handle_flags():
    """
    Process command line arguments
    :return: the dictionary of processed arguments
    """
    parser = ArgumentParser()

    parser.add_argument('-e', '--effort', type=int, default=9, choices=range(1, 10),
                        help='Encoder effort setting. Default 9.')
    parser.add_argument('-E', '--modular_nb_prev_channels', type=int, default=3,
                        help='[modular encoding] number of extra MA tree properties to use.'
                             'Default 3.')
    parser.add_argument('--brotli_effort', type=int, default=11, choices=range(1, 12),
                        help='Brotli effort setting. Default 11.')
    parser.add_argument('-j', '--lossless_jpeg', type=int, default=1, choices=range(0, 2),
                        help='If the input is JPEG, losslessly transcode JPEG, rather than using'
                             'reencoded pixels. 0 - Rencode, 1 - lossless. Default 1.')
    parser.add_argument('-m', '--modular', type=int, choices=range(0, 2),
                        help='Use modular mode (not provided = encoder chooses, 0 = enforce VarDCT'
                        ', 1 = enforce modular mode).')
    parser.add_argument('-t', '--threads', type=int, default=mp.cpu_count(),
                        help='The number of images to compress at once. Defaults to cpu threads.')
    parser.add_argument('--num_threads', type=int,
                        help='Number of threads to use to compress one image.'
                        'Defaults to (cpu threads) / --threads')
    parser.add_argument('-O', '--overwrite-destination', action='store_true',
                        help='Overwrite the destination, if it exists. Default False')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('output_directory', type=str, help='Output directory', nargs='?')
    group.add_argument('-o', '--overwrite', action='store_true',
                        help='Overwrite the original file. Default False.'
                       'Can only be passed if outputting to a folder')

    quality = parser.add_mutually_exclusive_group()
    quality.add_argument('-d', '--distance', type=int, default=0,
                         help='Max. butteraugli distance, lower = higher quality.  Default 0.')
    quality.add_argument('-q', '--quality', type=float,
    help='Quality setting, higher value = higher quality. This is internally mapped to --distance.'
    '100 = mathematically lossless. 90 = visually lossless.'
    'Quality values roughly match libjpeg quality.'
    'Recommended range: 68 .. 96. Allowed range: 0 .. 100. Mutually exclusive with --distance.')


    args = parser.parse_args()

    cwd = Path.cwd().as_posix()

    if args.overwrite_destination and not args.output_directory:
        raise ValueError('Overwrite destination can only be used when outputting to a folder.')

    if not args.overwrite:
        args.output_directory = Path(args.output_directory).as_posix()

    if not args.num_threads:
        args.num_threads = mp.cpu_count() // args.threads

    return args


def get_output_filename(args, input_file, working_directory):
    """
    Create a name for the output zip
    :param args: program arguments
    :param input_file: the path to the cbz file to be transcoded
    :param working_directory: the directory the program was run
    :return: the name of the zip file to write to
    """
    directory = working_directory

    if args.overwrite:
        directory /= input_file.parent
        tmp_zip = NamedTemporaryFile(dir=directory, prefix='.' + input_file.name, delete=False).name
        return working_directory / tmp_zip

    directory /= args.output_directory
    os.makedirs(directory / input_file.parent, exist_ok=True)

    if args.overwrite_destination:
        directory /= input_file.parent
        tmp_zip = NamedTemporaryFile(dir=directory, prefix='.' + input_file.name, delete=False).name
        return working_directory / tmp_zip

    name = directory / input_file
    name = name.with_suffix('.cbz')

    if name.exists():
        raise FileExistsError(f'File exists - {name}')
    return name


def statistics_string(original_size, compressed_size, prefix):
    """
    Return a statistics string, e.g.:
    A.cbz - 10/15 (-5) [MiB] 67%
    :param prefix: what string to include at the beginning
    """

    # to MiB
    difference = compressed_size - original_size
    quotient = round(compressed_size / original_size * 100)
    original_size = round(original_size / 1024 / 1024)
    compressed_size = round(compressed_size / 1024 / 1024)
    difference = round(difference / 1024 / 1024)

    return (prefix + ' - ' +
        f'{compressed_size}/{original_size}' +
        f' ({difference}) [MiB]' +
        f' {quotient}%')


def compress_comic(input_file, args):
    """
    Compress a comic book
    :param input_file: the comic book to compress
    :param args: compression arguments
    :return: the name of the compressed file
    """
    base = Path.cwd().resolve()

    try:
        with (
            TemporaryDirectory() as original_tmp,
        ):

            original_tmp = Path(original_tmp)
            unpack(input_file, original_tmp)
            clean_tmp_dir(original_tmp)
            os.chdir(original_tmp)
            compressed_name = transcode(input_file, args, base)
            os.chdir(base)
    except:
        os.chdir(base)
        original_tmp = Path(original_tmp)
        if original_tmp.exists():
            original_tmp.unlink()
        raise

    return compressed_name


def copy_files(zip_buffer):
    """
    Copy some files from the original comic book without changing them
    :param processed_dir: the directory to copy to
    """
    extensions = ['.txt', '.xml', '.jxl']
    files = [file for file in glob_relative('*') if file.suffix.lower() in extensions]
    with zipfile.ZipFile(zip_buffer, 'a', compression=zipfile.ZIP_STORED) as zipf:
        for file in files:
            zipf.write(file)


def stringify_arguments(args):
    """
    Changes all the arguments inside argparse.Namespace into strings
    """
    return Namespace(**{k: str(v) for k, v in vars(args).items()})


def transcode_file(input_file, args, lock, zip_file):
    """
    Compress a single image file
    :param input_file: the file to compress
    :param tmp_dir: the directory to compress it to
    :param args: the compression arguments to pass to cjxl
    :return: the compressed size
    """
    try:
        output_file = input_file.with_suffix('.jxl')

        cjxl_output = '/dev/stdout' if Path('/dev/stdout').exists() else '-'


        program_string = [
            'cjxl',
            '--brotli_effort',
            args.brotli_effort,
            '-e',
            args.effort,
            '-E',
            args.modular_nb_prev_channels,
            '--num_threads',
            args.num_threads,
            '-j',
            args.lossless_jpeg,
        ]

        if args.modular != 'None':
            program_string.append('-m')
            program_string.append(args.modular)

        if args.distance != 'None':
            program_string.append('-d')
            program_string.append(args.distance)
        else:
            program_string.append('-q')
            program_string.append(args.quality)

        program_string.append(input_file)
        program_string.append(cjxl_output)

        cjxl_process = subprocess.run(
            program_string,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        #if cjxl_process.returncode:
        #    print(cjxl_process.stderr)
        #    raise RuntimeError('File not transcoded')

        with lock:
            with zipfile.ZipFile(zip_file, 'a', compression=zipfile.ZIP_STORED) as zipf:
                zipf.writestr(str(output_file), cjxl_process.stdout)
    except KeyboardInterrupt:
        pass


def transcode(input_file, args, base):
    """
    Compress all the image files in the current directory
    :param args: compression arguments to pass to cjxl
    :return: the name of the compressed file
    """
    original_size = os.path.getsize(base / input_file)

    extensions = ['.gif', '.jpg', '.jpeg', '.png']
    files = [f for f in glob_relative('*') if f.suffix.lower() in extensions and f.is_file()]

    with (
            mp.Pool(args.threads) as pool,
            TextBar(total=len(files), text=input_file.name, unit='img', colour='#ff004c') as pbar,
            mp.Manager() as manager
            ):

        try:
            output_file = get_output_filename(args, input_file, base)
        except FileExistsError as e:
            pbar.close()
            print(e)
            return ''

        def update_bar(*a):
            pbar.update()

        def error_handler(err):
            print(err)
            pool.terminate()

        lock = manager.Lock()

        args = stringify_arguments(args)
        try:
            for file in files:
                #transcode_file(file, tmp_dir, args, lock, zip_buffer)
                pool.apply_async(transcode_file,
                                 (file, args, lock, output_file),
                                 callback=update_bar,
                                 error_callback=error_handler
                                 )
            pool.close()
            # one of the processess is the sync manager
            while len(mp.active_children()) > 1:
                pbar.refresh()
                sleep(0.5)
            pool.join()

            copy_files(output_file)

            check_transcoding(output_file)
            compressed_size = os.path.getsize(output_file)
            if args.overwrite == 'True':
                move(output_file, base / input_file)
            elif args.overwrite_destination == 'True':
                move(output_file, base / Path(args.output_directory) / input_file.with_suffix('.cbz'))
            pbar.close(text=statistics_string(original_size, compressed_size, input_file.name),
                       filled=True)
        except:
            pool.terminate()
            if Path(output_file).exists():
                output_file.unlink()
            raise

    if args.overwrite == 'True':
        return input_file
    if args.overwrite_destination == 'True':
        return Path(args.output_directory) / input_file.with_suffix('.cbz')
    return output_file


def compress_all_comics(args, directory):
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

    files = [file for file in glob_relative('*') if file.is_file()]

    comic_books = []
    for file in files:
        if (file.suffix.lower() in ['.cbr', '.cbz'] and
            (args.overwrite or Path(args.output_directory) not in file.parents)
            ):
            comic_books.append(file)

    original_size = sum([os.path.getsize(f) for f in comic_books])
    compressed_size = 0

    with TextBar(total=len(comic_books),
                 text='Comic books',
                 position=2,
                 unit='book',
                 colour='#ff004c') as pbar:
        for book in comic_books:
            try:
                compressed_name = compress_comic(book, args)
            except:
                raise
            compressed_size += os.path.getsize(compressed_name if compressed_name else book)
            pbar.display('', 1) # clear position 1
            pbar.update()

        pbar.display('', 2)
        pbar.close(text=statistics_string(original_size, compressed_size, 'Comic books'))


def main():
    """
    Compress all cbz/cbr files in the current directory
    """
    args = handle_flags()
    try:
        compress_all_comics(args, Path.cwd())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
