"""Handle files and images."""
import abc
import csv
import fnmatch
import logging
import os
import re
import time
from collections import defaultdict

import numpy as np
import tifffile
from PIL import Image

_LOGGER = logging.getLogger(__name__)


# def check_list(fnc):
#    """Decorator function for the functions in the Base class
#    and its subclasses."""
#
#    def wrapper(self, *args, **kwargs):
#        """Wrapper function in the decorator.
#        Runs the function fnc for all paths in path_list and returns
#        a list with the result."""
#        result = []
#        for path in self.path_list:
#            self.path = path
#            result.append(fnc(self, *args, **kwargs))
#        return result
#    return wrapper


class Base(object):
    """Base class.

    Attributes:
        path: A string representing the path to the object.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, path):
        """Set up instance."""
        self.path = path

    def get_dir(self, path=None):
        """Return parent directory."""
        if path is None:
            path = self.path
        return os.path.dirname(path)

    @abc.abstractmethod
    def get_name(self, regex, path):
        """Return the part of the name of the object, matching regex."""
        match = re.search(regex, os.path.basename(path))
        if match:
            return match.group()
        else:
            _LOGGER.warning('No search match: %s at: %s', regex, path)
            return None

    @abc.abstractmethod
    def base_type(self):
        """"Return a string representing the type of object this is."""
        pass


class Directory(Base):
    """A directory on the plate."""

    def get_children(self):
        """Return a list of child directories at path."""
        return [os.path.join(self.path, f) for f in os.listdir(self.path)
                if os.path.isdir(os.path.join(self.path, f))]

    def get_all_children(self):
        """Return a recursive list of child directories at path."""
        dir_list = []
        for root, dirnames, _ in os.walk(self.path):
            for dirname in dirnames:
                dir_list.append(os.path.join(root, dirname))
        return dir_list

    def get_name(self, regex, path=None):
        """Return regex match of the name of the path directory."""
        if path is None:
            path = self.path
        path = os.path.normpath(path)
        return super(Directory, self).get_name(regex, path)

    def get_files(self, regex):
        """Return a list of all files matching regex at path."""
        return [os.path.join(self.path, f)
                for f in fnmatch.filter(os.listdir(self.path), regex)
                if os.path.isfile(os.path.join(self.path, f))]

    def get_all_files(self, regex):
        """Return a list of all files matching regex, recursively, at path."""
        file_list = []
        for root, _, filenames in os.walk(self.path):
            for filename in fnmatch.filter(filenames, regex):
                file_list.append(os.path.join(root, filename))
        return file_list

    def base_type(self):
        """"Return a string representing the type of object this is."""
        return 'directory'


class File(Base):
    """A file."""

    def read_csv(self, index, header, path=None):
        """Read a csv file and return a defaultdict of lists."""
        if path is None:
            path = self.path
        dict_list = defaultdict(list)
        with open(path) as f:
            reader = csv.DictReader(f)
            for d in reader:
                for key in header:
                    dict_list[d[index]].append(d[key])
        return dict_list

    def write_csv(self, d, header, path=None):
        """Function to write a defaultdict of lists as a csv file."""
        if path is None:
            path = self.path
        with open(path, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for key, value in d.iteritems():
                writer.writerow([key] + value)
        return

    def get_name(self, regex, path=None):
        """Return the part of the name of the file, matching regex."""
        if path is None:
            path = self.path
        return super(File, self).get_name(regex, path)

    def base_type(self):
        """"Return a string representing the type of object this is."""
        return 'file'


class CamImage(Base):
    """An image."""

    def __init__(self, path):
        """Set up instance."""
        super(CamImage, self).__init__(path)
        self.name = self.get_name('image--.*.tif')
        # Should we use a string including the identifying letter or just
        # the number (int) for the ids?
        self.O_id = self.get_name(r'O\d\d')
        self.E_id = self.get_name(r'E\d\d')
        self.E_id_int = int(re.sub(r'\D', '', self.get_name(r'E\d\d')))
        self.J_id = self.get_name(r'J\d\d')
        self.well = self.get_name(r'U\d\d--V\d\d')
        self.field = self.get_name(r'X\d\d--Y\d\d')
        self.Z_id = self.get_name(r'Z\d\d')
        self.C_id = self.get_name(r'C\d\d')
        self.field_path = self.get_dir()
        self.well_path = self.get_dir(path=self.field_path)

    def read_image(self, path=None):
        """Read a tif image and return the data."""
        if path is None:
            path = self.path
        return np.array(Image.open(path))

    def meta_data(self, path=None):
        """Read a tif image and return the meta data of the description."""
        if path is None:
            path = self.path
        with tifffile.TiffFile(path) as tif:
            return tif[0].image_description

    def save_image(self, data, metadata=None, path=None):
        """Save a tif image with image data and meta data."""
        # if metadata is None: # description not always needed
        #    metadata = ''
        if path is None:
            path = self.path
        tifffile.imsave(path, data, description=metadata)
        return

    def get_name(self, regex, path=None):
        """Return the part of the name of the image, matching regex."""
        if path is None:
            path = self.path
        return super(CamImage, self).get_name(path, regex)

    def make_proj(self, path_list):
        """Make a dict of max projections from a list of image paths.

        Each channel will make one max projection.
        """
        _LOGGER.info('Making max projections')
        ptime = time.time()
        sorted_images = defaultdict(list)
        max_imgs = {}
        for path in path_list:
            channel = self.get_name(r'C\d\d', path=path)
            sorted_images[channel].append(self.read_image(path=path))
            max_imgs[channel] = np.max(sorted_images[channel], axis=0)
        _LOGGER.debug('Max proj: %s secs', str(time.time() - ptime))
        return max_imgs

    # #FIXME:0 Finish adding functions in image.py, trello:rigYhKuF

    def base_type(self):
        """"Return a string representing the type of object this is."""
        return 'image'
