"""Test automations."""
import pytest
from mock import patch

from camacq import sample as sample_mod
from camacq import api, automations
from camacq.control import CamAcqStartEvent

# pylint: disable=redefined-outer-name


class MockApi(api.Api):
    """Represent a mock microscope API."""

    def __init__(self):
        """Set up instance."""
        self.calls = []

    def send(self, command):
        """Send a command to the microscope API.

        Parameters
        ----------
        command : str
            The command to send.
        """
        self.calls.append((self.send.__name__, command))

    def start_imaging(self):
        """Send a command to the microscope to start the imaging."""
        self.calls.append((self.start_imaging.__name__, ))

    def stop_imaging(self):
        """Send a command to the microscope to stop the imaging."""
        self.calls.append((self.stop_imaging.__name__, ))


@pytest.fixture
def mock_api(center):
    """Set up a mock api."""
    _mock_api = MockApi()

    def setup_mock_api_package(center, config, add_child=None):
        """Set up a mock api package."""
        add_child('test_api', _mock_api)

    with patch('camacq.api.leica.setup_package') as leica_setup:
        leica_setup.side_effect = setup_mock_api_package
        api.setup_package(center, {'api': {'leica': None}})
        yield _mock_api


def test_setup_automation(center):
    """Test setup of an automation."""
    config = {
        'automations': [{
            'name': 'test_automation',
            'trigger': [{
                'type': 'event',
                'id': 'camacq_start_event',
            }],
            'action': [{
                'type': 'sample',
                'id': 'set_well',
                'data': {
                    'plate_name': 'test',
                    'well_x': 1,
                    'well_y': 1,
                },
            }],
        }],
    }

    sample_mod.setup_module(center, config)
    assert 'set_well' in center.actions.actions['sample']
    automations.setup_package(center, config)
    assert 'toggle' in center.actions.actions['automations']
    automation = center.data['camacq.automations']['test_automation']
    assert automation.enabled

    center.sample.set_plate('test')
    assert not center.sample.all_wells('test')
    event = CamAcqStartEvent({'test_data': 'start'})
    center.bus.notify(event)
    wells = center.sample.all_wells('test')
    assert wells[0].x == 1
    assert wells[0].y == 1

    center.actions.call('automations', 'toggle', name='test_automation')
    assert not automation.enabled


def test_channel_event(center, mock_api):
    """Test a trigger for channel event."""

    config = {
        'automations': [{
            'name': 'set_channel_gain',
            'trigger': [{
                'type': 'event',
                'id': 'channel_event',
            }],
            'action': [{
                'type': 'command',
                'id': 'send',
                'data': {
                    'command': (
                        "/cmd:adjust /tar:pmt "
                        "/num:{% if trigger.event.channel_name == 'green' %}1"
                        "{% elif trigger.event.channel_name == 'blue' %}1 "
                        "{% elif trigger.event.channel_name == 'yellow' %}2"
                        "{% elif trigger.event.channel_name == 'red' %}2"
                        "{% endif %} /exp:gain_job /prop:gain "
                        "/value:{{ trigger.event.channel.gain }}"),
                },
            }],
        }],
    }

    sample_mod.setup_module(center, config)
    automations.setup_package(center, config)
    automation = center.data['camacq.automations']['set_channel_gain']
    assert automation.enabled

    center.sample.set_plate('test')
    center.sample.set_channel(1, 1, 'yellow', 'test', gain=333)
    wells = center.sample.all_wells('test')
    assert wells[0].x == 1
    assert wells[0].y == 1
    assert 'send' in center.actions.actions['command']
    assert len(mock_api.calls) == 1
    func_name, command = mock_api.calls[0]
    assert func_name == 'send'
    assert command == (
        '/cmd:adjust /tar:pmt /num:2 /exp:gain_job /prop:gain /value:333')


def test_condition(center, mock_api):
    """Test a condition for command event."""

    config = {
        'automations': [{
            'name': 'add_exp_job',
            'trigger': [{
                'type': 'event',
                'id': 'command_event',
            }],
            'condition': {
                'type': 'AND',
                'conditions': [
                    {'condition':
                     "{% if 'test' in trigger.event.data %}true{% endif %}"},
                    {'condition':
                     "{% if trigger.event.data.test == 1 %}true{% endif %}"},
                ],
            },
            'action': [{
                'type': 'command',
                'id': 'send',
                'data': {
                    'command': 'success',
                },
            }],
        }],
    }

    sample_mod.setup_module(center, config)
    automations.setup_package(center, config)
    automation = center.data['camacq.automations']['add_exp_job']
    assert automation.enabled

    assert 'send' in center.actions.actions['command']
    center.bus.notify(api.CommandEvent(data={'test': 1}))
    assert len(mock_api.calls) == 1
    func_name, command = mock_api.calls[0]
    assert func_name == 'send'
    assert command == 'success'


def test_nested_condition(center, mock_api):
    """Test a nested condition for command event."""

    config = {
        'automations': [{
            'name': 'add_exp_job',
            'trigger': [{
                'type': 'event',
                'id': 'command_event',
            }],
            'condition': {
                'type': 'AND',
                'conditions': [
                    {'condition':
                     "{% if 'test' in trigger.event.data %}true{% endif %}"},
                    {
                        'type': 'OR',
                        'conditions': [
                            {'condition':
                             "{% if trigger.event.data.test == 1 %}true"
                             "{% endif %}"},
                            {'condition':
                             "{% if trigger.event.data.test == 2 %}true"
                             "{% endif %}"},
                        ],
                    },
                ],
            },
            'action': [{
                'type': 'command',
                'id': 'send',
                'data': {
                    'command': 'success',
                },
            }],
        }],
    }

    sample_mod.setup_module(center, config)
    automations.setup_package(center, config)
    automation = center.data['camacq.automations']['add_exp_job']
    assert automation.enabled
    assert 'send' in center.actions.actions['command']

    # This should not add a call to the api.
    center.bus.notify(api.CommandEvent(data={'test': 0}))

    assert not mock_api.calls

    # This should add a call to the api.
    center.bus.notify(api.CommandEvent(data={'test': 1}))

    assert len(mock_api.calls) == 1
    func_name, command = mock_api.calls[-1]
    assert func_name == 'send'
    assert command == 'success'

    # This should add a call to the api.
    center.bus.notify(api.CommandEvent(data={'test': 2}))

    assert len(mock_api.calls) == 2
    func_name, command = mock_api.calls[-1]
    assert func_name == 'send'
    assert command == 'success'

    # This should not add a call to the api.
    center.bus.notify(api.CommandEvent(data={'test': 3}))

    assert len(mock_api.calls) == 2


def test_sample_access(center, mock_api):
    """Test accessing sample in template."""

    config = {
        'automations': [{
            'name': 'set_img_ok',
            'trigger': [{
                'type': 'event',
                'id': 'image_event',
            }],
            'condition': {
                'type': 'AND',
                'conditions': [
                    {'condition':
                     "{% if not sample.plates[trigger.event.plate_name].wells["
                     "(trigger.event.well_x, trigger.event.well_y)].fields["
                     "(trigger.event.field_x, trigger.event.field_y)].img_ok "
                     "%}true{% endif %}"},
                ],
            },
            'action': [{
                'type': 'sample',
                'id': 'set_field',
                'data': {
                    'plate_name': '00',
                    'well_x': "{{ trigger.event.well_x }}",
                    'well_y': "{{ trigger.event.well_y }}",
                    'field_x': "{{ trigger.event.field_x }}",
                    'field_y': "{{ trigger.event.field_y }}",
                    'img_ok': True,
                },
            }],
        }],
    }

    sample_mod.setup_module(center, config)
    automations.setup_package(center, config)
    automation = center.data['camacq.automations']['set_img_ok']
    assert automation.enabled
    center.sample.set_plate('00')
    center.sample.set_well(0, 0, plate_name='00')
    field = center.sample.set_field(0, 0, 1, 1, img_ok=False)
    assert not field.img_ok

    center.bus.notify(api.leica.LeicaImageEvent(data={
        'path': 'image--L0000--S00--U00--V00--J15--E04--O01'
                '--X01--Y01--T0000--Z00--C00.ome.tif'}))
    field = center.sample.get_field(0, 0, 1, 1, plate_name=None)
    assert field.img_ok
