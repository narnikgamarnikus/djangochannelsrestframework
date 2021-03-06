import asyncio

import pytest
from channels import DEFAULT_CHANNEL_LAYER
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.contrib.auth import user_logged_in, get_user_model
from django.utils.text import slugify

from djangochannelsrestframework.consumers import AsyncAPIConsumer
from djangochannelsrestframework.observer import observer, model_observer


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_observer_wrapper(settings):
    settings.CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
            "TEST_CONFIG": {
                "expiry": 100500,
            },
        },
    }

    layer = channel_layers.make_test_backend(DEFAULT_CHANNEL_LAYER)

    class TestConsumer(AsyncAPIConsumer):

        async def accept(self):
            await TestConsumer.handle_user_logged_in.subscribe(self)
            await super().accept()

        @observer(user_logged_in)
        async def handle_user_logged_in(self, *args, observer=None, **kwargs):
            await self.send_json({
                    'message': kwargs,
                    'observer': observer is not None
                }
            )

    communicator = WebsocketCommunicator(TestConsumer, "/testws/")

    connected, _ = await communicator.connect()

    assert connected

    user = await database_sync_to_async(get_user_model().objects.create)(
        username='test',
        email='test@example.com'
    )

    await database_sync_to_async(user_logged_in.send)(
        sender=user.__class__,
        request=None,
        user=user
    )

    response = await communicator.receive_json_from()

    assert {'message': {}, 'observer': True} == response

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_model_observer_wrapper(settings):
    settings.CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
            "TEST_CONFIG": {
                "expiry": 100500,
            },
        },
    }

    layer = channel_layers.make_test_backend(DEFAULT_CHANNEL_LAYER)

    class TestConsumer(AsyncAPIConsumer):

        async def accept(self):
            await TestConsumer.user_change.subscribe(self)
            await super().accept()

        @model_observer(get_user_model())
        async def user_change(self, message, observer=None, **kwargs):
            await self.send_json(message)

    communicator = WebsocketCommunicator(TestConsumer, "/testws/")

    connected, _ = await communicator.connect()

    assert connected

    user = await database_sync_to_async(get_user_model().objects.create)(
        username='test',
        email='test@example.com'
    )

    response = await communicator.receive_json_from()

    assert {
               'action': 'create',
               'pk': user.pk,
               'type': 'user.change'
           } == response

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_model_observer_delete_wrapper(settings):
    settings.CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
            "TEST_CONFIG": {
                "expiry": 100500,
            },
        },
    }

    layer = channel_layers.make_test_backend(DEFAULT_CHANNEL_LAYER)

    class TestConsumer(AsyncAPIConsumer):

        async def accept(self):
            await TestConsumer.user_change.subscribe(self)
            await super().accept()

        @model_observer(get_user_model())
        async def user_change(self, message, observer=None, **kwargs):
            await self.send_json(message)

    communicator = WebsocketCommunicator(TestConsumer, "/testws/")

    connected, _ = await communicator.connect()

    assert connected
    print("before create ---------------")
    user = await database_sync_to_async(get_user_model())(
        username='test',
        email='test@example.com'
    )
    print('not saved yet ------' )
    await database_sync_to_async(user.save)()
    print("after create ---------------")

    response = await communicator.receive_json_from()

    assert {
               'action': 'create',
               'pk': user.pk,
               'type': 'user.change'
           } == response
    pk = user.pk

    await database_sync_to_async(user.delete)()

    response = await communicator.receive_json_from()

    assert {
        'action': 'delete',
        'pk': pk,
        'type': 'user.change'
    } == response

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_model_observer_many_connections_wrapper(settings):
    settings.CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
            "TEST_CONFIG": {
                "expiry": 100500,
            },
        },
    }

    layer = channel_layers.make_test_backend(DEFAULT_CHANNEL_LAYER)

    class TestConsumer(AsyncAPIConsumer):

        async def accept(self):
            await TestConsumer.user_change.subscribe(self)
            await super().accept()

        @model_observer(get_user_model())
        async def user_change(self, message, **kwargs):
            await self.send_json(message)

    communicator1 = WebsocketCommunicator(TestConsumer, "/testws/")

    connected, _ = await communicator1.connect()

    assert connected

    communicator2 = WebsocketCommunicator(TestConsumer, "/testws/")

    connected, _ = await communicator2.connect()

    assert connected

    user = await database_sync_to_async(get_user_model().objects.create)(
        username='test',
        email='test@example.com'
    )

    response = await communicator1.receive_json_from()

    assert {
               'action': 'create',
               'pk': user.pk,
               'type': 'user.change'
           } == response

    await communicator1.disconnect()

    response = await communicator2.receive_json_from()

    assert {
               'action': 'create',
               'pk': user.pk,
               'type': 'user.change'
           } == response

    await communicator2.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_model_observer_many_consumers_wrapper(settings):
    settings.CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
            "TEST_CONFIG": {
                "expiry": 100500,
            },
        },
    }

    layer = channel_layers.make_test_backend(DEFAULT_CHANNEL_LAYER)

    class TestConsumer(AsyncAPIConsumer):

        async def accept(self):
            await self.user_change.subscribe()
            await super().accept()

        @model_observer(get_user_model())
        async def user_change(self, message, **kwargs):
            await self.send_json(message)

    class TestConsumer2(AsyncAPIConsumer):

        async def accept(self):
            await self.user_other.subscribe()
            await super().accept()

        @model_observer(get_user_model())
        async def user_other(self, message, **kwargs):
            await self.send_json(message)

    communicator1 = WebsocketCommunicator(TestConsumer, "/testws/")

    connected, _ = await communicator1.connect()

    assert connected

    communicator2 = WebsocketCommunicator(TestConsumer2, "/testws/")

    connected, _ = await communicator2.connect()

    assert connected

    user = await database_sync_to_async(get_user_model().objects.create)(
        username='test',
        email='test@example.com'
    )

    response = await communicator1.receive_json_from()

    assert {
               'action': 'create',
               'pk': user.pk,
               'type': 'user.change'
           } == response

    await communicator1.disconnect()

    response = await communicator2.receive_json_from()

    assert {
               'action': 'create',
               'pk': user.pk,
               'type': 'user.other'
           } == response

    await communicator2.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_model_observer_custom_groups_wrapper(settings):
    settings.CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
            "TEST_CONFIG": {
                "expiry": 100500,
            },
        },
    }

    layer = channel_layers.make_test_backend(DEFAULT_CHANNEL_LAYER)

    class TestConsumer(AsyncAPIConsumer):

        async def accept(self):
            await self.user_change.subscribe(username='test')
            await super().accept()

        @model_observer(get_user_model())
        async def user_change(self, message, **kwargs):
            await self.send_json(message)

        @user_change.groups
        def user_change(self, instance=None, username=None, **kwargs):
            if username:
                yield '-instance-username-{}'.format(slugify(username))
            else:
                yield '-instance-username-{}'.format(instance.username)

    communicator = WebsocketCommunicator(TestConsumer, "/testws/")

    connected, _ = await communicator.connect()

    assert connected

    user = await database_sync_to_async(get_user_model().objects.create)(
        username='test',
        email='test@example.com'
    )

    response = await communicator.receive_json_from()

    assert {
               'action': 'create',
               'pk': user.pk,
               'type': 'user.change'
           } == response

    await communicator.disconnect()

    user = await database_sync_to_async(get_user_model().objects.create)(
        username='test2',
        email='test@example.com'
    )

    # no event since this is only subscribed to 'test'
    with pytest.raises(asyncio.TimeoutError):
        await communicator.receive_json_from()
