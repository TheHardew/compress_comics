#!/usr/bin/env python

import os
from shutil import copy
import subprocess
from pathlib import Path
from multiprocessing import Pool
from functools import partial
from tempfile import TemporaryDirectory
import sys
import zipfile
from argparse import ArgumentParser


def unpack(f, tmp_dir):
    mime_type = subprocess.run(["file", "--mime-type", "-b", str(f)], capture_output=True, text=True).stdout.strip()

    if mime_type == "application/zip":
        subprocess.run(["unzip", "-oO", "GB18030", str(f), "-d", str(tmp_dir)])
    elif mime_type == "application/x-rar":
        subprocess.run(["unrar", "x", "-o+", str(f), str(tmp_dir)])


def clean_tmp_dir(tmp_dir):
    for file in tmp_dir.glob('*.sfv'):
        file.unlink()
    for file in tmp_dir.glob('Thumbs.db'):
        file.unlink()


def check_file_types(tmp_dir):
    extensions = ['.gif', '.jpg', '.jpeg', '.png', '.jxl', '.xml', '.txt']
    if any(file.suffix.lower() not in extensions for file in tmp_dir.glob('**/*') if file.is_file()):
        raise Exception(f'{file} is not jpg/png/jxl/xml/txt')

def check_transcoding(tmp_dir):
    source_files = len([file for file in Path.cwd().glob('**/*') if file.is_file()])
    jxl_files = len([file for file in tmp_dir.glob('**/*') if file.is_file()])
    if source_files != jxl_files:
        raise Exception('not all files transcoded - exiting')


def handle_flags(args):
    name = args[0]
    parser = ArgumentParser()
    # TODO handle any flags
    parser.add_argument('-e', '--effort',  type=int, help=f'Encoder effort setting. Range: 1 .. 9. Default 9.', default=9)
    parser.add_argument('-E', '--modular_nb_prev_channels',  type=int, help=f'usage: {name}. [modular encoding] number of extra MA tree properties to use. Default 3.', default=3)
    parser.add_argument('--brotli_effort',  type=int, help=f'usage: {name}. Brotli effort setting. Range: 0 .. 11. Default 11.', default=11)
    parser.add_argument('-d' '--distance',  help=f'usage: {name}. Max. butteraugli distance, lower = higher quality. Default 0.', default=0)
    parser.add_argument('-j' '--lossless_jpeg',  help=f'usage: {name}. If the input is JPEG, losslessly transcode JPEG, rather than using reencode pixels. Default 0.', default=1)
    parser.add_argument('output_directory', type=str, help='Output drectory')
    args = parser.parse_args()

    if 'help' in args:
        parser.print_help()
        exit()
    return args


def compress_cbz(input_file, args):
    base = Path.cwd()
    output_dir_absolute = Path(args.output_directory).resolve()
    os.makedirs(output_dir_absolute / input_file.parent, exist_ok=True)

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
        copy_files(original_tmp, processed_tmp)

        # shouldn't be necessary because the program checks the exit status
        check_transcoding(processed_tmp) 
        pack(input_file, output_dir_absolute, processed_tmp)

    os.chdir(base)


def copy_files(original_dir, processed_dir):
    extensions = ['.txt', '.xml', '.jxl']
    files = [file.relative_to(original_dir) for file in original_dir.glob('**/*') if file.suffix.lower() in extensions and file.is_file()]
    for file in files:
        copy(file, processed_dir)


def transcode_file(input_file, tmp_dir, args):
    output_file = tmp_dir / input_file
    output_file = output_file.with_suffix('.jxl')
    result = subprocess.run([
        'cjxl',
        '--brotli_effort',
        str(args.brotli_effort),
        '-d',
        str(args.d__distance),
        '-e',
        str(args.effort),
        '-E',
        str(args.modular_nb_prev_channels),
        '--num_threads',
        '0',
        '-j',
        str(args.j__lossless_jpeg),
        input_file,
        str(output_file),
        ])

    if result.returncode:
        raise Exception(f'Non zero exit status on {input_file}')


def error_handler(pool, err):
    print(err)
    pool.terminate()


def transcode(tmp_dir, args):
    extensions = ['.gif', '.jpg', '.jpeg', '.png']

    cwd = Path.cwd()
    files = [file.relative_to(cwd) for file in cwd.glob('**/*') if file.suffix.lower() in extensions and file.is_file()]

    for dir in cwd.glob('**/*/'):
        dir = dir.relative_to(cwd)
        os.makedirs(tmp_dir / dir, exist_ok=True)

    with Pool() as pool:
        handler = partial(error_handler, pool)
        for file in files:
            pool.apply_async(transcode_file, args=(file, tmp_dir, args, ), error_callback = handler)
        pool.close()
        pool.join()


def pack(input_file, output_dir, processed_tmp):
    os.chdir(processed_tmp)
    output_file = output_dir / input_file
    output_file.with_suffix('.zip')

    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_STORED) as zipf:
        for file in processed_tmp.glob('**/*'):
            file = file.relative_to(processed_tmp)
            zipf.write(file, arcname=file)


def main():
    if (len(sys.argv) < 2):
        sys.argv.append('-h')
        handle_flags(sys.argv[0])

    args = handle_flags(sys.argv)
    cwd = Path.cwd()
    args.output_directory = str(Path(args.output_directory).resolve().relative_to(cwd))

    output_dir = Path(sys.argv[1])
    cwd = Path.cwd()
    for comic in cwd.glob('**/*.cbz'):
        comic = comic.relative_to(cwd)
        if str(comic).startswith(args.output_directory):
            continue
        compress_cbz(comic, args)

if __name__ == "__main__":
    main()
