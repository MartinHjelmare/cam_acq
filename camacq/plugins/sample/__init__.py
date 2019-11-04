"""Handle sample state."""
import asyncio
import logging
from abc import ABC, abstractmethod

import voluptuous as vol

from camacq.exceptions import SampleError
from camacq.helper import BASE_ACTION_SCHEMA

_LOGGER = logging.getLogger(__name__)

ACTION_SET_SAMPLE = "set_sample"
DATA_SAMPLE = "sample"
SAMPLE_STATE_FILE = "state_file"
SET_SAMPLE_ACTION_SCHEMA = BASE_ACTION_SCHEMA.extend(
    {"sample_name": vol.Coerce(str)}, extra=vol.ALLOW_EXTRA
)

ACTION_TO_METHOD = {
    ACTION_SET_SAMPLE: {"method": "set_sample", "schema": SET_SAMPLE_ACTION_SCHEMA},
}


async def setup_module(center, config):
    """Set up sample module.

    Parameters
    ----------
    center : Center instance
        The Center instance.
    config : dict
        The config dict.
    """
    sample_store = center.data.setdefault(DATA_SAMPLE, {})

    async def handle_action(**kwargs):
        """Handle action call to add a state to the sample.

        Parameters
        ----------
        **kwargs
            Arbitrary keyword arguments. These will be passed to a
            method when an action is called.
        """
        action_id = kwargs.pop("action_id")
        method = ACTION_TO_METHOD[action_id]["method"]
        sample_name = kwargs.pop("sample_name", None)
        if sample_name:
            samples = [sample_store[sample_name]]
        else:
            samples = list(sample_store.values())
        tasks = []
        for sample in samples:
            try:
                kwargs = sample.set_sample_schema(kwargs)
            except vol.Invalid as exc:
                _LOGGER.error(
                    "Invalid action call parameters %s: %s for action: %s.%s",
                    kwargs,
                    exc,
                    "sample",
                    action_id,
                )
                continue

            _LOGGER.debug(
                "Handle sample %s action %s: %s", sample.name, action_id, kwargs
            )
            tasks.append(center.create_task(getattr(sample, method)(**kwargs)))
        if tasks:
            await asyncio.wait(tasks)

    for action_id, options in ACTION_TO_METHOD.items():
        schema = options["schema"]
        center.actions.register("sample", action_id, handle_action, schema)


class Samples:
    """Hold all samples."""

    # pylint: disable=too-few-public-methods

    def __init__(self, center):
        """Set up the instance."""
        self._center = center

    def __getattr__(self, sample_name):
        """Get a sample by name."""
        sample = self._center.data.get(DATA_SAMPLE, {}).get(sample_name)

        if sample is None:
            raise SampleError(f"Unable to get sample with name {sample_name}")

        return sample


def register_sample(center, sample):
    """Register sample."""
    sample.center = center
    center.bus.register(sample.image_event_type, sample.on_image)
    sample_store = center.data.setdefault(DATA_SAMPLE, {})
    sample_store[sample.name] = sample


class ImageContainer(ABC):
    """A container for images."""

    @property
    @abstractmethod
    def change_event(self):
        """:Event: Return an event that should be fired on container change."""

    @property
    @abstractmethod
    def images(self):
        """:dict: Return a dict with all images for the container."""


class Sample(ImageContainer, ABC):
    """Representation of the state of the sample."""

    center = None

    @property
    @abstractmethod
    def image_event_type(self):
        """:str: Return the image event type to listen to for the sample."""

    @property
    @abstractmethod
    def name(self):
        """Return the name of the sample."""

    @property
    @abstractmethod
    def set_sample_schema(self):
        """Return the validation schema of the set_sample method."""

    @abstractmethod
    async def on_image(self, center, event):
        """Handle image event for this sample."""

    async def set_sample(self, **values):
        """Set an image container of the sample.

        Returns
        -------
        ImageContainer instance
            Return the ImageContainer instance that was updated.
        """
        container = self._set_sample(**values)
        await self.center.bus.notify(container.change_event)
        return container

    @abstractmethod
    def _set_sample(self, **values):
        """Set an image container of the sample.

        Returns
        -------
        ImageContainer instance
            Return the ImageContainer instance that was updated.
        """


class Image(ABC):
    """An image with path and position info.

    Parameters
    ----------
    path : str
        Path to the image.


    Attributes
    ----------
    path : str
        The path to the image.
    """

    # pylint: disable=too-many-arguments, too-few-public-methods
    # pylint: disable=too-many-instance-attributes

    def __repr__(self):
        """Return the representation."""
        return "<Image(path={0!r})>".format(self.path)

    @property
    @abstractmethod
    def path(self):
        """Return the path of the image."""
