from pathlib import Path
import multiprocessing as mp
from argparse import ArgumentParser, Namespace, REMAINDER, HelpFormatter
from collections import defaultdict


class CustomHelpFormatter(HelpFormatter):
    def format_help(self):
        help_str = super().format_help()
        help_str = help_str.replace('...', 'INPUT')
        return help_str


class ArgumentGroupParser:
    def __init__(self):
        self.parser = ArgumentParser(formatter_class=CustomHelpFormatter)
        self.groups = {}
        self.parents = {}
        self.parent_groups = []
        self.group_keys = defaultdict(list)

    def add_argument_group(self, name, description):
        self.groups[name] = self.parser.add_argument_group(name, description)
        self.parent_groups.append(name)
        self.parents[name] = name

    @staticmethod
    def _derive_dest(*args, **kwargs):
        dest = kwargs.get('dest')
        if dest:
            return dest

        option_strings = [arg for arg in args if arg.startswith('-')]

        if option_strings:
            dest = next((s for s in option_strings if s.startswith('--')), option_strings[0])
        else:
            dest = args[0]

        dest = dest.lstrip('-')
        dest = dest.replace('-', '_')
        return dest

    def add_mutually_exclusive_group(self, parent, name, required=False):
        self.groups[name] = self.groups[parent].add_mutually_exclusive_group(required=required)
        self.parents[name] = parent

    def add_argument(self, group, *args, **kwargs):
        self.groups[group].add_argument(*args, **kwargs)
        parent = self.parents[group]
        key = ArgumentGroupParser._derive_dest(*args, **kwargs)
        self.group_keys[parent].append(key)

    def parse_args(self):
        argument_groups = {}
        args = self.parser.parse_args()
        for group in self.parent_groups:
            argument_groups[group] = {}
            for k, v in vars(args).items():
                if k in self.group_keys[group]:
                    argument_groups[group][k] = v

            argument_groups[group] = Namespace(**argument_groups[group])

        return argument_groups


def parse_args():
    parser = ArgumentGroupParser()

    parser.add_argument_group('program options', 'Options influencing program behaviour')
    parser.add_argument('program options', '-t', '--threads', type=int, default=mp.cpu_count(),
                        help='The number of images to compress at once. Defaults to cpu threads.')
    parser.add_argument('program options', '-O', '--output_directory', type=Path, default='.',
                        help='Output directory. Defaults to current directory.'
                             '\nNeeds the -o flag to overwrite source.')
    parser.add_argument('program options', '-o', '--overwrite', action='store_true',
                        help='Overwrite the original file. Default: False.')
    parser.add_argument('program options', 'INPUT', type=Path, nargs=REMAINDER,
                        default='.',
                        help='Input file/directory. Defaults to the current directory (.)')

    parser.add_argument_group('cjxl options', 'Options passed to the cjxl encoder')
    parser.add_argument('cjxl options', '-e', '--effort', type=int, choices=range(1, 11),
                        help='Encoder effort setting.\n'
                             'Effort 10 requires --allow_expert_options')
    parser.add_argument('cjxl options', '-E', '--modular_nb_prev_channels', type=int,
                        help='[modular encoding] number of extra MA tree properties to use.')
    parser.add_argument('cjxl options', '--brotli_effort', type=int, choices=range(1, 12),
                        help='Brotli effort setting.')
    parser.add_argument('cjxl options', '-j', '--lossless_jpeg', type=int, default=1, choices=range(0, 2),
                        help='If the input is JPEG, losslessly transcode JPEG, rather than using '
                             'reencoded pixels. 0 - Rencode, 1 - lossless. Default: 1.')
    parser.add_argument('cjxl options', '-m', '--modular', type=int, choices=range(0, 2),
                        help='Use modular mode (0 = enforce VarDCT, 1 = enforce modular mode).')
    parser.add_argument('cjxl options', '--num_threads', type=int, default=None,
                        help='Number of threads to use to compress one image. '
                             'Default: (cpu threads) / --threads')

    parser.add_mutually_exclusive_group('cjxl options', 'quality')
    parser.add_argument('quality', '-d', '--distance', type=int, default=0,
                        help='Max. butteraugli distance, lower = higher quality.  Default: 0.')
    parser.add_argument('quality', '-q', '--quality', type=float,
                        help='Quality setting, higher value = higher quality. '
                             'This is internally mapped to --distance.'
                             '\n100 = mathematically lossless. 90 = visually lossless.'
                             '\nQuality values roughly match libjpeg quality.'
                             '\nRecommended range: 68 .. 96. Allowed range: 0 .. 100. '
                             'Mutually exclusive with --distance.')

    argument_groups = parser.parse_args()
    program_args = argument_groups['program options']
    encoder_args = argument_groups['cjxl options']
    program_args.output_directory = program_args.output_directory.resolve()

    if not program_args.INPUT:
        program_args.INPUT.append(Path('.'))
    program_args.INPUT = map(lambda p: p.resolve(), program_args.INPUT)

    if program_args.output_directory == Path('.').resolve() and not program_args.overwrite:
        raise ValueError('The -o flag is needed to overwrite source files')

    if encoder_args.num_threads is None:
        encoder_args.num_threads = mp.cpu_count() // program_args.threads

    return program_args, encoder_args


def handle_flags():
    """
    Process command line arguments
    :return: the dictionary of processed arguments
    """

    program_args, encoder_args = parse_args()
    return program_args, encoder_args
