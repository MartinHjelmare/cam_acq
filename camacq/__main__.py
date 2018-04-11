"""Main module."""
from __future__ import print_function

import argparse
import logging
import os
import sys

import camacq.bootstrap as bootstrap
import camacq.config as config_util
from camacq.const import CONFIG_DIR, LOG_LEVEL


def check_dir_arg(path):
    """Check that argument is a directory."""
    # remove if not needed
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(
            'String {} is not a path to a directory'.format(path))


def check_log_level(loglevel):
    """Validate log level and return it if valid."""
    # assuming loglevel is bound to the string value obtained from the
    # command line argument. Convert to upper case to allow the user to
    # specify --log=DEBUG or --log=debug
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise argparse.ArgumentTypeError(
            'String {} is not a valid log level'.format(loglevel))
    else:
        return numeric_level


def parse_command_line():
    """Parse the provided command line."""
    parser = argparse.ArgumentParser(
        description='Control microscope through client-server program.')
    parser.add_argument(
        '--log-level',
        dest=LOG_LEVEL,
        type=check_log_level,
        help='an option to specify lowest log level to log')
    parser.add_argument(
        '-C',
        '--config',
        dest=CONFIG_DIR,
        default=config_util.get_default_config_dir(),
        help='the path to camacq configuration directory')
    args = parser.parse_args()
    if args.config_dir:
        args.config_dir = os.path.normpath(args.config_dir)
    cmd_args_dict = vars(args)
    cmd_args_dict = {
        key: val for key, val in cmd_args_dict.items() if val}

    return cmd_args_dict


def ensure_config_path(config_dir):
    """Validate the configuration directory."""
    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        if config_dir != config_util.get_default_config_dir():
            print(('Fatal Error: Specified configuration directory does '
                   'not exist {} ').format(config_dir))
            sys.exit(1)

        try:
            os.mkdir(config_dir)
        except OSError:
            print(('Fatal Error: Unable to create default configuration '
                   'directory {} ').format(config_dir))
            sys.exit(1)


def ensure_config_file(config_dir):
    """Ensure configuration file exists."""
    config_path = config_util.ensure_config_exists(config_dir)

    if config_path is None:
        print('Error getting configuration path')
        sys.exit(1)

    return config_path


def main():
    """Main function."""
    # Parse command line arguments
    cmd_args = parse_command_line()
    config_dir = os.path.join(os.getcwd(), cmd_args[CONFIG_DIR])
    ensure_config_path(config_dir)
    config_file = ensure_config_file(config_dir)
    center = bootstrap.setup_file(config_file, cmd_args)
    if not center:
        print('Could not load config file at:', config_file)
        sys.exit(1)
    center.start()
    return center.exit_code


if __name__ == '__main__':
    main()
