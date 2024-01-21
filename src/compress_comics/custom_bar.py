"""
A module for superimposing text in the middle of progress bars
"""
import shutil


def get_background_color_string(hex_color):
    """
    Create a shell escape code to change the background color based on a hex color string
    :param hex_color: the color to set the background to
    :return: the shell escape code
    """
    red = int(hex_color[1:3], 16)
    green = int(hex_color[3:5], 16)
    blue = int(hex_color[5:], 16)
    hex_string = f'{red};{green};{blue}'
    return f'\x1b[97;48;2;{hex_string}m'


def get_base_bar_length(pbar, bar_format):
    """
    Return the bar length based on bar_format
    :param pbar: the progress bar used to calculate the length of the bar
    :param bar_format: the custom format used for calculating the length
    :return: the length
    """
    pbar.bar_format = bar_format
    base_bar_length = len(str(pbar))
    if pbar.n == 0:
        base_bar_length += 8
    return base_bar_length


def get_custom_progress_bar(text, pbar, bar_format):
    """
    Retrun a custom progress bar format encoding text in the middle of the progress  bar
    :param text: the text to be superimposed on the bar
    :param pbar: the progress bar to modify
    :param bar_format: the format to modify
    :return: the custom progress bar format
    """
    background_color = get_background_color_string(pbar.colour)
    reset_color = '\x1b[0m'

    base_bar_length = get_base_bar_length(pbar, bar_format)
    bar_length = shutil.get_terminal_size().columns - base_bar_length
    custom_bar = text + ' ' * (bar_length - len(text))

    filled_in = round(bar_length * pbar.n / pbar.total)
    return background_color + custom_bar[:filled_in] + reset_color + custom_bar[filled_in:]


def custom_bar_format(text, pbar):
    """
    Retrun a custom bar format encoding text in the middle of the progress  bar
    :param text: the text to be superimposed on the bar
    :param pbar: the progress bar to modify
    :return: the custom bar format
    """
    # sets width for the number of current items to match the width of total items
    width = len(str(pbar.total))
    r_bar = f'| {pbar.n: >{width}}/' + '{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
    bar_format = '{l_bar}' + f'{r_bar}'

    return '{l_bar}' + get_custom_progress_bar(' ' + text, pbar, bar_format) + r_bar
