"""Helper functions for camacq."""
import logging
import pkgutil
import signal
import sys
from importlib import import_module

import voluptuous as vol

import camacq

_LOGGER = logging.getLogger(__name__)

PACKAGE_MODULE = "{}.{}"
BASE_ACTION_SCHEMA = vol.Schema({"action_id": str}, extra=vol.REMOVE_EXTRA)
CORE_MODULES = ["api", "sample"]


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
    matches = [
        name
        for _, name, _ in pkgutil.walk_packages(
            camacq.__path__, prefix="{}.".format(camacq.__name__)
        )
        if module_path in name
    ]
    if len(matches) != 1:
        raise ValueError("Invalid module search result, not a single match")
    module_path = matches[0]
    try:
        module = import_module(module_path)
        _LOGGER.debug("Loaded %s from %s", module_name, module_path)

        return module

    except ImportError:
        _LOGGER.exception(("Loading %s failed"), module_path)


async def setup_one_module(center, config, module):
    """Set up one module or package.

    Returns
    -------
    asyncio.Task
        Return a task to set up the module or None.
    """
    module_name = module.__name__.split(".")[-1]
    if not hasattr(module, "setup_module"):
        _LOGGER.warning("Missing setup_module function in module %s", module_name)
        return
    _LOGGER.info("Setting up module %s", module_name)
    if hasattr(module, "CONFIG_SCHEMA"):
        _LOGGER.debug("Validating config for module %s", module_name)
        module_conf = config[module_name]
        try:
            module_conf = await center.add_executor_job(
                module.CONFIG_SCHEMA, module_conf
            )
        except vol.Invalid as exc:
            _LOGGER.error("Incorrect configuration for module %s: %s", module_name, exc)
            return
        config[module_name] = module_conf
    await module.setup_module(center, config)


def register_signals(center):
    """Register signal handlers."""
    if sys.platform != "win32":

        def handle_signal(exit_code):
            """Handle a signal."""
            center.loop.remove_signal_handler(signal.SIGTERM)
            center.loop.remove_signal_handler(signal.SIGINT)
            center.create_task(center.end(exit_code))

        center.loop.add_signal_handler(signal.SIGTERM, handle_signal, 0)
        center.loop.add_signal_handler(signal.SIGINT, handle_signal, 0)

    else:

        prev_sig_term = None
        prev_sig_int = None

        def handle_signal(signum, frame):
            """Handle a signal."""
            signal.signal(signal.SIGTERM, prev_sig_term)
            signal.signal(signal.SIGINT, prev_sig_int)
            center.create_task(center.end(signum))

        prev_sig_term = signal.signal(signal.SIGTERM, handle_signal)
        prev_sig_int = signal.signal(signal.SIGINT, handle_signal)
