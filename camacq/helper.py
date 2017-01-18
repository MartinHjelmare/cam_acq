"""Helper functions for camacq."""
import csv
import logging
import os
import re
from collections import defaultdict

from matrixscreener import experiment

_LOGGER = logging.getLogger(__name__)


def send(cam, commands):
    """Send each command in commands.

    Parameters
    ----------
    cam : instance
        CAM instance.
    commands : list
        List of list of commands as tuples.

    Returns
    -------
    list
        Return a list of OrderedDict with all received replies.

    Example
    -------
    ::

        send(cam, [[('cmd', 'deletelist')], [('cmd', 'startscan')]])
    """
    replies = []
    for cmd in commands:
        _LOGGER.debug(cmd)
        reply = cam.send(cmd)
        _LOGGER.debug(reply)
        if reply:
            replies.extend(reply)
    return replies


def read_csv(path, index, header):
    """Read a csv file and return a defaultdict of lists.

    Parameters
    ----------
    path : string
        Path to csv file.
    index : string
        Index can be any of the column headers of the csv file.
        The column under index will be used as keys in the returned
        defaultdict.
    header : list
        List of strings with any of the column headers of the csv file,
        except index. Each item in header will be used to add the
        corresponding column and row value to the list of the row in the
        returned defaultdict.

    Returns
    -------
    defaultdict(list)
        Return a defaultdict of lists with the contents of the csv file,
        indicated by the index and header parameters. Each item in the
        defaultdict will represent a row or part of a row from the csv file.
    """
    dict_list = defaultdict(list)
    with open(path) as file_handle:
        reader = csv.DictReader(file_handle)
        for dictionary in reader:
            for key in header:
                dict_list[dictionary[index]].append(dictionary[key])
    return dict_list


def write_csv(path, dict_list, header):
    """Write a defaultdict of lists as a csv file.

    Parameters
    ----------
    path : string
        Path to csv file.
    dict_list : defaultdict(list)
        The defaultdict of lists that should be written as a csv file.
    header : list
        List of strings with the wanted column headers of the csv file.
        The items in header should correspond to the key of the dictionary
        and all items in the list for a key.
    """
    with open(path, 'wb') as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(header)
        for key, value in dict_list.iteritems():
            writer.writerow([key] + value)


def find_image_path(reply, root):
    """Parse the reply from the server to find the correct file path."""
    paths = reply.split('\\')
    for path in paths:
        root = os.path.join(root, path)
    return str(root)


def format_new_name(imgp, root=None, new_attr=None):
    """Create filename from image path and replace specific attribute id(s).

    Parameters
    ----------
    imgp : string
        Path to image.
    root : string
        Path to directory where path should start.
    new_attr : dict
        Dictionary which maps experiment attributes to new attribute ids.
        The new attribute ids will replace the old ids for the corresponding
        attributes.

    Returns
    -------
    string
        Return new path to image.
    """
    if root is None:
        root = get_field(imgp)

    path = 'U{}--V{}--E{}--X{}--Y{}--Z{}--C{}.ome.tif'.format(
        *(experiment.attribute_as_str(imgp, attr)
          for attr in ('U', 'V', 'E', 'X', 'Y', 'Z', 'C')))
    if new_attr:
        for attr, attr_id in new_attr.iteritems():
            path = re.sub(
                attr + r'\d\d', attr + attr_id, path)

    return os.path.normpath(os.path.join(root, path))


def rename_imgs(imgp, f_job):
    """Rename image and return new name."""
    if experiment.attribute(imgp, 'E') == f_job:
        new_name = format_new_name(imgp)
    elif (experiment.attribute(imgp, 'E') == f_job + 1 and
          experiment.attribute(imgp, 'C') == 0):
        new_name = format_new_name(imgp, new_attr={'C': '01'})
    elif (experiment.attribute(imgp, 'E') == f_job + 1 and
          experiment.attribute(imgp, 'C') == 1):
        new_name = format_new_name(imgp, new_attr={'C': '02'})
    elif experiment.attribute(imgp, 'E') == f_job + 2:
        new_name = format_new_name(imgp, new_attr={'C': '03'})
    else:
        return None
    os.rename(imgp, new_name)
    return new_name


def get_field(path):
    """Get path to well from image path."""
    return experiment.Experiment(path).dirname  # pylint: disable=no-member


def get_well(path):
    """Get path to well from image path."""
    # pylint: disable=no-member
    return experiment.Experiment(get_field(path)).dirname


def get_imgs(path, img_type='tif', search=''):
    """Get all images below path."""
    if search:
        search = '{}*'.format(search)
    patterns = [
        'slide',
        'chamber',
        'field',
        'image',
    ]
    for pattern in patterns:
        if pattern not in path:
            path = os.path.join(path, '{}--*'.format(pattern))
    return experiment.glob('{}{}.{}'.format(path, search, img_type))
