"""Test the event bus."""
from camacq import event as event_mod


def test_event_bus(center):
    """Test register handler, fire event and remove handler."""
    event = event_mod.Event({'test': 2})
    bus = center.bus

    def handler(center, event):
        """Handle event."""
        if 'test' not in center.data:
            center.data['test'] = 0
        center.data['test'] += event.data['test']

    assert event_mod.BASE_EVENT not in bus.event_types

    remove = bus.register(event_mod.BASE_EVENT, handler)

    assert event_mod.BASE_EVENT in bus.event_types
    assert not center.data

    bus.notify(event)
    center.run_all()

    assert center.data.get('test') == 2

    remove()
    bus.notify(event)
    center.run_all()

    assert center.data.get('test') == 2
