"""Helper functions for camacq."""
import csv
import logging
import os
import pkgutil
from collections import defaultdict
from importlib import import_module

import camacq
from camacq.const import PACKAGE

_LOGGER = logging.getLogger(__name__)

_MODULE_CACHE = {}
PACKAGE_MODULE = '{}.{}'


def call_saved(job):
    """Call a saved job of a tuple with func and args.

    Parameters
    ----------
    job : tuple
        A tuple of a callable and possibly arguments to pass to the
        callable.
    """
    func = job[0]
    if len(job) > 1:
        args = job[1:]
    else:
        args = ()
    _LOGGER.debug('Calling: %s(%s)', func, args)
    return func(*args)


def get_module(package, module_name):
    """Return a module from a package.

    Parameters
    ----------
    package : str
        The path to the package.
    module_name : str
        The name of the module.
    """
    module_path = PACKAGE_MODULE.format(package, module_name)
    if module_path in _MODULE_CACHE:
        return _MODULE_CACHE[module_path]
    matches = [
        name for _, name, _
        in pkgutil.walk_packages(
            camacq.__path__, prefix='{}.'.format(camacq.__name__))
        if module_path in name]
    if len(matches) > 1:
        raise ValueError('Invalid module search result, more than one match')
    module_path = matches[0]
    if module_path in _MODULE_CACHE:
        return _MODULE_CACHE[module_path]
    try:
        module = import_module(module_path)
        _LOGGER.info("Loaded %s from %s", module_name, module_path)
        _MODULE_CACHE[module_path] = module

        return module

    except ImportError:
        _LOGGER.exception(('Loading %s failed'), module_path)


def _deep_conf_access(config, key_list):
    """Return value in nested dict using keys in key_list."""
    val = config
    for key in key_list:
        _val = val.get(key)
        if _val is None:
            return val
        val = _val
    return val


def setup_all_modules(center, config, package_path, **kwargs):
    """Helper to set up all modules of a package.

    Parameters
    ----------
    center : Center instance
        The Center instance.
    config : dict
        The config dict.
    package_path : str
        The path to the package.
    **kwargs
        Arbitrary keyword arguments. These will be passed to
        setup_package and setup_module functions.
    """
    imported_pkg = import_module(package_path)
    # yields, non recursively, modules under package_path
    for loader, name, is_pkg in pkgutil.iter_modules(
            imported_pkg.__path__, prefix='{}.'.format(imported_pkg.__name__)):
        if 'main' in name:
            continue
        if name in _MODULE_CACHE:
            module = _MODULE_CACHE[name]
        else:
            module = loader.find_module(name).load_module(name)
            _MODULE_CACHE[name] = module
        _LOGGER.info('Loaded %s', name)
        keys = [
            name for name in imported_pkg.__name__.split('.')
            if name != PACKAGE]
        pkg_config = _deep_conf_access(config, keys)
        if module.__name__.split('.')[-1] in pkg_config:
            if is_pkg and hasattr(module, 'setup_package'):
                _LOGGER.info('Setting up %s', module.__name__)
                module.setup_package(center, config, **kwargs)
            elif hasattr(module, 'setup_module'):
                _LOGGER.info('Setting up %s', module.__name__)
                module.setup_module(center, config, **kwargs)


def read_csv(path, index):
    """Read a csv file and return a dict of dicts.

    Parameters
    ----------
    path : str
        Path to csv file.
    index : str
        Index can be any of the column headers of the csv file.
        The column under index will be used as keys in the returned
        dict.

    Returns
    -------
    defaultdict(dict)
        Return a dict of dicts with the contents of the csv file,
        indicated by the index parameter. Each item in the dict will
        represent a row, with index as key, of the csv file.
    """
    csv_map = defaultdict(dict)
    path = os.path.normpath(path)
    with open(path) as file_handle:
        reader = csv.DictReader(file_handle)
        for row in reader:
            key = row.pop(index)
            csv_map[key].update(row)
    return csv_map


def write_csv(path, csv_map, header):
    """Write a dict of dicts as a csv file.

    Parameters
    ----------
    path : str
        Path to csv file.
    csv_map : dict(dict)
        The dict of dicts that should be written as a csv file.
    header : list
        List of strings with the wanted column headers of the csv file.
        The items in header should correspond to the index key of the
        primary dict and all the keys of the secondary dict.
    """
    with open(path, 'wb') as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=header)
        writer.writeheader()
        for index, cells in csv_map.iteritems():
            index_dict = {header[0]: index}
            index_dict.update(cells)
            writer.writerow(index_dict)


def handler_factory(center, handler, test):
    """Create handler that should call another handler if test is True.

    Parameters
    ----------
    center : Center instance
        The Center instance.
    handler : callable
        The function that should handle the event.
    test : callable
        A function that should test if the handler should be called.
        The function should accept the event.

    Returns
    -------
    callable
        Return a function that can be used as an event handler. The
        function will call another handler only if the test returns
        True.
    """
    def handle_test(center, event):
        """Forward event to handler if test is True."""
        if test(event):
            handler(center, event)
    return handle_test


def add_fields(well, fields_x, fields_y):
    """Add a number of fields in a well with some default values.

    Field 0, 0 and field 1, 1 will be set as gain_field.

    Parameters
    ----------
    well : Well instance
        Well instance where to add the fields.
    fields_x : int
        Number of fields in x to add.
    fields_y : int
        Number of fields in y to add.
    """
    for i in range(fields_y):
        for j in range(fields_x):
            well.set_field(
                j, i, 0, 0, j == 0 and i == 0 or j == 1 and i == 1)


class FeatureParent(object):
    """Represent a parent of features of a package.

    Attributes
    ----------
    children : dict
        Return dict of children of the parent.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self):
        """Set up the feature parent."""
        self.children = {}

    def add_child(self, child_name, child):
        """Add a child to the parent feature registry.

        A child is the instance that provides a feature, eg a
        microscope API.

        Parameters
        ----------
        child_name : str
            Name of the child. The name will be the key in the registry
            dict.
        child : child instance
            The instance of the child that should be stored.
        """
        self.children[child_name] = child
