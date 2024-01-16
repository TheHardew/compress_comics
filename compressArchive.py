#!/usr/bin/env python

import os
import subprocess
from pathlib import Path
from multiprocessing import Pool
from functools import partial
import tempfile
import sys
import zipfile

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


def compress_cbz(input_file, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    output_dir_absolute = output_dir.resolve()

    with (
            tempfile.TemporaryDirectory() as original_tmp,
            tempfile.TemporaryDirectory() as processed_tmp
    ):
        original_tmp = Path(original_tmp)
        processed_tmp = Path(processed_tmp)
        unpack(input_file, original_tmp)
        clean_tmp_dir(original_tmp)
        check_file_types(original_tmp)

        base = Path.cwd()
        os.chdir(original_tmp)
        transcode(processed_tmp)

        # shouldn't be necessary because the program checks the exit status
        check_transcoding(processed_tmp) 
        pack(input_file, output_dir_absolute, processed_tmp)


def transcode_file(input_file, output_dir):
    output_file = output_dir / input_file
    output_file = output_file.with_suffix('.jxl')
    result = subprocess.run([
        'cjxl',
        '--brotli_effort',
        '11',
        '-d',
        '0',
        '-e',
        '1',
        '-E',
        '3',
        '--num_threads',
        '0',
        input_file,
        output_file,
        ])

    if result.returncode:
        raise Exception(f'Non zero exit status on {input_file}')


def error_handler(pool, err):
    print(err)
    pool.terminate()


def transcode(tmp_dir):
    extensions = ['.gif', '.jpg', '.jpeg', '.png']

    cwd = Path.cwd()
    files = [file.relative_to(cwd) for file in cwd.glob('**/*') if file.suffix.lower() in extensions and file.is_file()]

    for dir in cwd.glob('**/*/'):
        dir = dir.relative_to(cwd)
        os.makedirs(tmp_dir / dir, exist_ok=True)

    fun = partial(transcode_file, output_dir = tmp_dir)
    with Pool() as pool:
        handler = partial(error_handler, pool)
        for file in files:
            pool.apply_async(fun, args=(file, ), error_callback = handler)
        pool.close()
        pool.join()


    for file in cwd.glob('**/*'):
        if file.suffix.lower() in ['.txt', '.xml']:
            file = file.relative_to(cwd)
            shutil.copy(file, tmp_dir / file)


def pack(input_file, output_dir, processed_tmp):
    os.chdir(processed_tmp)
    output_file = output_dir / input_file
    output_file.with_suffix('.zip')

    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_STORED) as zipf:
        for file in processed_tmp.glob('**/*'):
            file = file.relative_to(processed_tmp)
            zipf.write(file, arcname=file)


def main():
    if (len(sys.argv) != 2):
        print(f'usage {sys.argv[0]} ouput_directory')
        exit()

    output_dir = Path(sys.argv[1])
    cwd = Path.cwd()
    for comic in cwd.glob('**/*.cbz'):
        comic = comic.relative_to(cwd)
        if str(comic).startswith(output_dir.name):
            continue
        compress_cbz(comic, output_dir)

if __name__ == "__main__":
    main()
