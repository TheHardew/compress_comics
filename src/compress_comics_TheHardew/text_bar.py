"""
A module for superimposing text in the middle of progress bars
"""
import shutil
from tqdm import tqdm


class TextBar(tqdm):
    """
    A class which puts text in the middle of the tqdm progress bar
    Manages updates to set the bar format correctly
    """
    def __get_background_color_string(self):
        """
        Create a shell escape code to change the background color
        :return: the shell escape code
        """
        red = int(self.colour[1:3], 16)
        green = int(self.colour[3:5], 16)
        blue = int(self.colour[5:], 16)
        hex_string = f'{red};{green};{blue}'
        return f'\x1b[97;48;2;{hex_string}m'


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
        Retrun a custom progress bar format encoding text in the middle of the progress bar
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


    def __custom_bar_format(self, filled=False):
        """
        Retrun a custom bar format encoding text in the middle of the progress  bar
        :return: the custom bar format
        """
        # sets width for the number of current items to match the width of total items
        width = len(str(self.total))
        if self.total == 0:
            l_bar = '100%|'
            remaining = '00:00'
        else:
            l_bar = '{l_bar}'
            remaining = '{remaining}'

        r_bar = f'| {self.n: >{width}}/' '{total_fmt} [{elapsed}<' \
                f'{remaining}' ', {rate_fmt}{postfix}]'
        bar_format = l_bar + r_bar

        return l_bar + self.__get_custom_progress_bar(bar_format, filled=filled) + r_bar

    def __init__(self, *, text='', **kwargs):
        """
        Initiazlise the text progress bar
        :param text: text to use
        """
        self.text = text
        super().__init__(**kwargs)
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
        if text:
            self.text = text
        self.bar_format = self.__custom_bar_format(filled)
        tqdm.close(self)


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
