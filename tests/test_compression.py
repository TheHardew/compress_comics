import compress_comics_TheHardew
from tempfile import TemporaryDirectory
import sys
from pathlib import Path
import zipfile


def get_zipfile_files(filepath):
    with zipfile.ZipFile(filepath, 'r') as zipf:
        return sorted(zipf.namelist())


# TODO maybe don't rely on the expected_files txt file
def test():
    with open('expected_files.txt', 'r') as file:
        expected_files =  sorted([line.strip() for line in file])

    with TemporaryDirectory() as tmpd:
        sys.argv = ['compress_comics', '-e1', '--brotli_effort', '1', tmpd]
        compress_comics_TheHardew.main()

        for file in Path.cwd().rglob('*'):
            if file.is_file() and file.suffix.lower() in ['.cbz', '.cbr']:
                file = file.with_suffix('.cbz')
                files = get_zipfile_files(Path(tmpd) / file.name)
                assert files == expected_files


if __name__ == "__main__":
    test()
