"""
A module for compressing a comic book
"""
import os
from shutil import move
import subprocess
from pathlib import Path
import multiprocessing as mp
from tempfile import TemporaryDirectory, NamedTemporaryFile
import zipfile
from patoolib import extract_archive
from .text_bar import TextBar
from time import sleep


def glob_relative(pattern):
    """
    Recursively get a relative list of files in the current directory matching a glob pattern
    """
    cwd = Path.cwd()
    return [f.relative_to(cwd) for f in Path.cwd().rglob(pattern)]


def statistics_string(compressed_size, original_size, prefix):
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


def _transcode_file(input_file, encoder_options, lock, zip_file):
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

        program_string = ['cjxl']

        for arg in vars(encoder_options):
            value = getattr(encoder_options, arg)
            if value is not None:
                program_string.append('--' + arg)
                program_string.append(str(value))

        program_string.append(input_file)
        program_string.append(cjxl_output)

        cjxl_process = subprocess.run(
            program_string,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # if cjxl_process.returncode:
        #    print(cjxl_process.stderr)
        #    raise RuntimeError('File not transcoded')

        with lock:
            with zipfile.ZipFile(zip_file, 'a', compression=zipfile.ZIP_STORED) as zipf:
                zipf.writestr(str(output_file), cjxl_process.stdout)
    except KeyboardInterrupt:
        pass


class ComicCompressor:
    def __init__(self, input_file, working_directory, program_options, encoder_options):
        self.input_file = Path(input_file)
        self.program_options = program_options
        self.encoder_options = encoder_options
        self.original_size = os.path.getsize(self.input_file)
        self.compressed_size = os.path.getsize(self.input_file)
        self.working_directory = working_directory
        self.output_file = self.__get_output_filename()

    def __unpack(self, directory):
        """
        Unpack a comic book to a directory
        """
        extract_archive(str(self.input_file), verbosity=-1, outdir=str(directory))

    def compress(self):
        """
        Compress a comic book
        :return: the name of the compressed file
        """
        base = Path.cwd().resolve()

        try:
            with (
                TemporaryDirectory() as unpacked_comic_dir,
            ):

                unpacked_comic_dir = Path(unpacked_comic_dir)
                self.__unpack(unpacked_comic_dir)
                ComicCompressor.__clean_tmp_dir(unpacked_comic_dir)
                os.chdir(unpacked_comic_dir)
                compressed_name = self.__transcode()
                os.chdir(base)
        except:
            os.chdir(base)
            unpacked_comic_dir = Path(unpacked_comic_dir)
            if unpacked_comic_dir.exists():
                unpacked_comic_dir.unlink()
            raise

        return compressed_name

    @staticmethod
    def __clean_tmp_dir(tmp_dir):
        """
        Remove useless files in the comic book.
        Removes Thumbs.db files and checksum (.sfv) files.
        :param tmp_dir: the directory to clean.
        """
        for file in tmp_dir.glob('*.sfv'):
            file.unlink()
        for file in tmp_dir.glob('Thumbs.db'):
            file.unlink()

    def __transcode(self):
        """
        Compress all the image files in the current directory
        :return: the name of the compressed file
        """
        extensions = ['.png', '.gif', '.jpg', '.jpeg']
        files = []
        # modular encoding should be carried out first for better performance
        for ext in extensions:
            files += [f for f in glob_relative('*') if f.is_file() and f.suffix.lower() == ext]

        directory = self.output_file.parent
        with (
            mp.Pool(self.program_options.threads) as pool,
            mp.Manager() as manager,
            TextBar(total=len(files), text=self.input_file.name, unit='img', colour='#ff004c') as pbar,
            TemporaryDirectory(dir=directory, prefix='.compressed_books') as tmp_dir,
        ):
            tmp_dir = Path(tmp_dir)
            temporary_output = tmp_dir / self.input_file.name

            def update_bar(*a):
                pbar.update()

            def error_handler(err):
                print(err)
                pool.terminate()

            lock = manager.Lock()

            try:
                for file in files:
                    # transcode_file(file, tmp_dir, args, lock, zip_buffer)
                    pool.apply_async(_transcode_file,
                                     (file, self.encoder_options, lock, temporary_output),
                                     callback=update_bar,
                                     error_callback=error_handler
                                     )
                pool.close()
                # one of the processes is the sync manager
                while len(mp.active_children()) > 1:
                    pbar.refresh()
                    sleep(0.5)
                pool.join()

                ComicCompressor.__copy_files(temporary_output)

                self.__check_transcoding(temporary_output)
                self.compressed_size = os.path.getsize(temporary_output)
                move(temporary_output, self.output_file)
                pbar.close(text=statistics_string(self.compressed_size, self.original_size, self.input_file.name))
            except:
                pool.terminate()
                raise

        return self.output_file

    def __get_output_filename(self):
        """
        Create a name for the output zip
        :return: the name of the zip file to write to
        """
        if self.program_options.overwrite:
            return self.input_file

        output_directory = self.program_options.output_directory.resolve()
        output_directory /= self.input_file.relative_to(self.working_directory).parent

        os.makedirs(output_directory, exist_ok=True)

        name = output_directory / self.input_file.with_suffix('.cbz').name

        if name.exists() and not self.program_options.overwrite_destination:
            raise FileExistsError(f'File exists - {name}')
        return name

    def __check_transcoding(self, output_file):
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

    @staticmethod
    def __copy_files(zip_buffer):
        """
        Copy some files from the original comic book without changing them
        :param processed_dir: the directory to copy to
        """
        extensions = ['.txt', '.xml', '.jxl']
        files = [file for file in glob_relative('*') if file.suffix.lower() in extensions]
        with zipfile.ZipFile(zip_buffer, 'a', compression=zipfile.ZIP_STORED) as zipf:
            for file in files:
                zipf.write(file)
