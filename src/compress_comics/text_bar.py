"""
A module for superimposing text in the middle of progress bars
"""
import shutil
from tqdm import tqdm
import time


class TextBar(tqdm):
    """
    A class which puts text in the middle of the tqdm progress bar
    Manages updates to set the bar format correctly
    """

    @staticmethod
    def __colors_from_rgb_hex(hex_color):
        """
        Parse a hex string int
        :param hex_color: a hex color string, e.g. #ABCDEF
        :return: the shell escape code
        """
        return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))

    def __get_background_color_string(self):
        """
        Create a shell escape code to change the background color
        :return: the shell escape code
        """
        colours = TextBar.__colors_from_rgb_hex(self.colour)
        return '\x1b[48;2;' + ';'.join(map(str, colours)) + 'm'

    @staticmethod
    def reset_line():
        print("\033[0m")

    def __get_foreground_color_string(self):
        """
        Create a shell escape code to change the foreground color
        :return: the shell escape code
        """
        colours = TextBar.__colors_from_rgb_hex(self.colour)
        return '\x1b[38;2;' + ';'.join(map(str, colours)) + 'm'

    def __get_base_bar_length(self, bar_format):
        """
        Return the bar length based on bar_format
        :param bar_format: the custom format used for calculating the length
        :return: the length
        """
        self.bar_format = bar_format
        base_bar_length = len(str(self))
        return base_bar_length

    def __get_custom_progress_bar(self, bar_format, filled=False):
        """
        Return a custom progress bar format encoding text in the middle of the progress bar
        :param bar_format: the format to modify
        :return: the custom progress bar format
        """
        background_color = self.__get_background_color_string()
        reset_color = '\x1b[0m'

        base_bar_length = self.__get_base_bar_length(bar_format)
        bar_length = shutil.get_terminal_size().columns - base_bar_length
        text = ' ' + self.text
        custom_bar = text + ' ' * (bar_length - len(text))

        if self.total:
            filled_in = round(bar_length * self.n / max(1, self.total))
        else:
            filled_in = bar_length if filled else 0
        return background_color + custom_bar[:filled_in] + reset_color + custom_bar[filled_in:]

    @staticmethod
    def __format_time(seconds):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        return_string = f'{int(minutes):02d}:{int(seconds):02d}'
        if hours > 0:
            return f'{int(hours):02d}:' + return_string
        return return_string

    def __calculate_remaining(self):
        avg_rate = self.__calculate_rate()
        if avg_rate == 0:
            return TextBar.__format_time(0)
        return TextBar.__format_time((self.total - self.n) / avg_rate)

    def __calculate_percentage(self):
        if self.total == 0:
            return 100
        return round(100 * self.n / self.total)

    def __format_elapsed(self):
        if self.n == 0:
            return TextBar.__format_time(0)

        elapsed = time.time() - self.start_time
        return TextBar.__format_time(elapsed)

    def __calculate_rate(self):
        elapsed = time.time() - self.start_time
        return self.n / elapsed if elapsed else 0

    def __custom_closed_bar_format(self, filled=False):
        """
        Return a custom bar format encoding text in the middle of the progress  bar
        :return: the custom bar format
        """
        # sets width for the number of current items to match the width of total items
        width = len(str(self.total))

        l_bar = self.__format_elapsed() + '|'
        rate = self.__calculate_rate()
        rate_unit = f'{self.unit}/s'
        if rate < 1 and rate != 0:
            rate = 1 / rate
            rate_unit = f's/{self.unit}'
        rate = f'{rate:.2f}'

        r_bar = f'| {self.n: >{width}}/{self.total} [{rate}{rate_unit}]'
        bar_format = l_bar + r_bar

        return l_bar + self.__get_custom_progress_bar(bar_format, filled=filled) + r_bar

    def __custom_bar_format(self, filled=False):
        """
        Return a custom bar format encoding text in the middle of the progress  bar
        :return: the custom bar format
        """
        # sets width for the number of current items to match the width of total items
        width = len(str(self.total))

        l_bar = f'{self.__calculate_percentage():3d}%' + '|'
        remaining = self.__calculate_remaining()
        elapsed = self.__format_elapsed()
        rate = self.__calculate_rate()
        rate_unit = f'{self.unit}/s'
        if rate < 1 and rate != 0:
            rate = 1 / rate
            rate_unit = f's/{self.unit}'

        rate = f'{rate:5.2f}'

        r_bar = f'| {self.n: >{width}}/{self.total} [{elapsed}<{remaining} {rate}{rate_unit}]'
        bar_format = l_bar + r_bar

        return l_bar + self.__get_custom_progress_bar(bar_format, filled=filled) + r_bar

    def __init__(self, *args, text='', **kwargs):
        """
        Initialize the text progress bar
        :param text: text to use
        """
        self.text = text
        self.start_time = time.time()
        self.running_times = [0]
        self.n = 0
        self.closed = False
        # self.position = 0
        super().__init__(*args, **kwargs)
        self.bar_format = self.__custom_bar_format()
        self.refresh()

    def refresh(self, **kwargs):
        """
        Display the progress bar
        """
        self.bar_format = self.__custom_bar_format()
        tqdm.refresh(self, **kwargs)

    def close(self, text=None, filled=False):
        """
        Close the bar while keeping the custom text or applying new one
        :param text: new text to apply. if None, use the old one
        """
        if self.closed:
            return

        if text:
            self.text = text

        if filled:
            self.bar_format = self.__custom_closed_bar_format(filled)
            tqdm.close(self)
        else:
            self.display('')
            self.bar_format = ''
            tqdm.close(self)
            print('\033[F\r\033[K', end='')
            print(f'{self.__format_elapsed()}|', self.text)

        self.closed = True

    def update(self, n=1, text=None):
        """
        Update the custom text bar
        :param n: how much to update by
        :param text: new text to be applied. if None, keep the old one
        """
        # clear the format so nothing is printed on update
        self.bar_format = ''
        tqdm.update(self, n)
        if text:
            self.text = text
        self.bar_format = self.__custom_bar_format()
        self.refresh()
