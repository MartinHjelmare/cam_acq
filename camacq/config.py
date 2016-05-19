"""Handle the config file."""
import logging
import os

import yaml
from pkg_resources import resource_filename

_LOGGER = logging.getLogger(__name__)

CONFIG_DIR_NAME = '.camacq'
YAML_CONFIG_FILE = 'config.yml'


def get_default_config_dir():
    """Get the default configuration directory based on OS."""
    data_dir = os.getenv('APPDATA') if os.name == 'nt' \
        else os.path.expanduser('~')
    return os.path.join(data_dir, CONFIG_DIR_NAME)


def find_config_file(config_dir):
    """Look in given directory for supported configuration files."""
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)

    return config_path if os.path.isfile(config_path) else None


def load_config_file(path):
    """Parse a YAML configuration file."""
    try:
        with open(path, 'r') as yml_file:
            cfg = yaml.safe_load(yml_file)
        if not isinstance(cfg, dict):
            _LOGGER.error(
                'The configuration file %s does not contain a dictionary',
                os.path.basename(path))
            raise TypeError()  # or let it pass?
        return cfg
    except yaml.YAMLError as exception:
        _LOGGER.error(
            'Error reading YAML configuration file %s', path)
        raise yaml.YAMLError(exception)  # or let it pass?


def create_default_config(config_dir):
    """Create a default configuration file in given configuration directory.

    Return path to new config file if success, None if failed.
    """
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)
    default_config_template = resource_filename(__name__, 'data/config.yml')
    data = load_config_file(default_config_template)

    try:
        with open(config_path, 'w') as config_file:
            config_file.write(yaml.dump(data, default_flow_style=True))

        return config_path

    except IOError:
        print('Unable to create default configuration file', config_path)
        return None


def ensure_config_exists(config_dir):
    """Ensure a config file exists in given configuration directory.

    Create a default one if needed.
    Return path to the config file.
    """
    config_path = find_config_file(config_dir)

    if config_path is None:
        print("Unable to find configuration. Creating default one in",
              config_dir)
        config_path = create_default_config(config_dir)

    return config_path
