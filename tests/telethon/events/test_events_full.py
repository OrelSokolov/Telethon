import pytest
import asyncio
import datetime
import struct
import re
import warnings
import time
import weakref
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from telethon import TelegramClient, events, types, utils


@pytest.fixture
def client():
    return TelegramClient(None, 1, '1')


@pytest.fixture
def mock_client(client):
    client._mb_entity_cache = MagicMock()
    client._albums = {}
    client.loop = asyncio.get_event_loop()
    return client


class TestCommonFull:
    @pytest.mark.asyncio
    async def test_into_id_set_with_self_peer(self):
        from telethon.events.common import _into_id_set
        client = TelegramClient(None, 1, '1')
        
        # Mock get_input_entity to return InputPeerSelf
        input_peer_self = types.InputPeerSelf()
        client.get_input_entity = AsyncMock(return_value=input_peer_self)
        
        result = await _into_id_set(client, 123)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_event_builder_resolve_lock(self):
        builder = events.NewMessage(chats=123)
        client = TelegramClient(None, 1, '1')
        client.get_input_entity = AsyncMock(return_value=None)
        
        # Multiple resolve calls should only resolve once
        task1 = asyncio.create_task(builder.resolve(client))
        task2 = asyncio.create_task(builder.resolve(client))
        
        await task1
        await task2
        assert builder.resolved is True

    @pytest.mark.asyncio
    async def test_event_builder_filter_with_chat_id_none(self):
        builder = events.NewMessage(chats={123})
        builder.resolved = True
        event = MagicMock()
        event.chat_id = None
        
        result = builder.filter(event)
        # Should return None because chat_id is None and not in chats
        assert result is None



class TestMessageReadFull:
    @pytest.mark.asyncio
    async def test_message_read_filter_with_chats_whitelist(self):
        builder = events.MessageRead(chats={123}, inbox=False)
        builder.resolved = True
        event = MagicMock()
        event.chat_id = 123
        event.outbox = True
        
        result = builder.filter(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_message_read_filter_with_chats_not_matched(self):
        builder = events.MessageRead(chats={123}, inbox=False)
        builder.resolved = True
        event = MagicMock()
        event.chat_id = 456
        event.outbox = True
        
        result = builder.filter(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_message_read_filter_blacklist(self):
        builder = events.MessageRead(chats={123}, inbox=False, blacklist_chats=True)
        builder.resolved = True
        event = MagicMock()
        event.chat_id = 123
        event.outbox = True
        
        result = builder.filter(event)
        # Should return None because chat_id matches blacklist
        assert result is None


class TestUserUpdateFull:
    @pytest.mark.asyncio
    async def test_user_update_event_get_user(self):
        event = events.UserUpdate.Event(peer=types.PeerUser(123))
        user = types.User(id=123, access_hash=456, first_name='Test')
        event._sender = user
        event._input_sender = types.InputPeerUser(user_id=123, access_hash=456)
        
        result = await event.get_user()
        assert result == user

    @pytest.mark.asyncio
    async def test_user_update_event_get_input_user(self):
        event = events.UserUpdate.Event(peer=types.PeerUser(123))
        input_user = types.InputPeerUser(user_id=123, access_hash=456)
        event._sender = types.User(id=123, access_hash=456)
        event._input_sender = input_user
        
        result = await event.get_input_user()
        assert result == input_user


class TestCallbackQueryFull:
    @pytest.mark.asyncio
    async def test_callback_query_event_answer_already_answered(self):
        query = types.UpdateBotCallbackQuery(
            query_id=1,
            user_id=123,
            peer=types.PeerUser(456),
            msg_id=789,
            chat_instance=0,
            data=b'test'
        )
        event = events.CallbackQuery.Event(query, types.PeerUser(456), 789)
        event._answered = True
        event._client = MagicMock()
        
        result = await event.answer(message='answer')
        # Should return None if already answered
        assert result is None

    @pytest.mark.asyncio
    async def test_callback_query_event_respond(self):
        query = types.UpdateBotCallbackQuery(
            query_id=1,
            user_id=123,
            peer=types.PeerUser(456),
            msg_id=789,
            chat_instance=0,
            data=b'test'
        )
        event = events.CallbackQuery.Event(query, types.PeerUser(456), 789)
        event._client = MagicMock()
        event._client.send_message = AsyncMock(return_value='result')
        event._client.loop = MagicMock()
        event._client.loop.create_task = lambda x: None
        
        result = await event.respond('test message')
        assert result == 'result'

    @pytest.mark.asyncio
    async def test_callback_query_event_reply(self):
        query = types.UpdateBotCallbackQuery(
            query_id=1,
            user_id=123,
            peer=types.PeerUser(456),
            msg_id=789,
            chat_instance=0,
            data=b'test'
        )
        event = events.CallbackQuery.Event(query, types.PeerUser(456), 789)
        event._client = MagicMock()
        event._client.send_message = AsyncMock(return_value='result')
        event._client.loop = MagicMock()
        event._client.loop.create_task = lambda x: None
        
        result = await event.reply('reply message')
        assert result == 'result'

    @pytest.mark.asyncio
    async def test_callback_query_event_edit(self):
        msg_id = types.InputBotInlineMessageID(id=123, dc_id=1, access_hash=456)
        query = types.UpdateInlineBotCallbackQuery(
            query_id=1,
            user_id=123,
            msg_id=msg_id,
            chat_instance=0,
            data=b'test'
        )
        event = events.CallbackQuery.Event(query, types.PeerUser(123), 789)
        event._client = MagicMock()
        event._client.edit_message = AsyncMock(return_value='result')
        event._client.loop = MagicMock()
        event._client.loop.create_task = lambda x: None
        
        result = await event.edit('new text')
        assert result == 'result'

    @pytest.mark.asyncio
    async def test_callback_query_event_delete_inline(self):
        msg_id = types.InputBotInlineMessageID(id=123, dc_id=1, access_hash=456)
        query = types.UpdateInlineBotCallbackQuery(
            query_id=1,
            user_id=123,
            msg_id=msg_id,
            chat_instance=0,
            data=b'test'
        )
        event = events.CallbackQuery.Event(query, types.PeerUser(123), 789)
        event._client = MagicMock()
        event._client.loop = MagicMock()
        event._client.loop.create_task = lambda x: None
        
        with pytest.raises(TypeError):
            await event.delete()

    @pytest.mark.asyncio
    async def test_callback_query_event_refetch_sender_no_sender(self):
        query = types.UpdateBotCallbackQuery(
            query_id=1,
            user_id=123,
            peer=types.PeerUser(456),
            msg_id=789,
            chat_instance=0,
            data=b'test'
        )
        event = events.CallbackQuery.Event(query, types.PeerUser(456), 789)
        event._chat = None
        event._client = MagicMock()
        
        # Should just return without error
        await event._refetch_sender()


class TestAlbumFull:
    def test_album_build_multiple_updates(self):
        message1 = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test1', out=False, grouped_id=999)
        message2 = types.Message(id=2, peer_id=types.PeerUser(123), date=None, message='test2', out=False, grouped_id=999)
        message3 = types.Message(id=3, peer_id=types.PeerUser(123), date=None, message='test3', out=False, grouped_id=888)
        
        update = types.UpdateNewMessage(message=message1, pts=0, pts_count=0)
        
        event = events.Album.build(update)
        # Should create event with only messages that match grouped_id
        assert event is not None
        assert len(event.messages) == 1
        assert event.messages[0].id == 1

    @pytest.mark.asyncio
    async def test_album_event_set_client(self):
        from telethon.events.album import Album
        
        message1 = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test1', out=False, grouped_id=999)
        message2 = types.Message(id=2, peer_id=types.PeerUser(123), date=None, message='test2', out=False, grouped_id=999)
        
        event = Album.Event([message1, message2])
        
        client = MagicMock()
        client._mb_entity_cache = MagicMock()
        client._albums = {}
        
        event._set_client(client)
        
        # Should finish init all messages
        for msg in event.messages:
            assert msg._client == client

    @pytest.mark.asyncio
    async def test_album_event_forward_to(self):
        from telethon.events.album import Album
        
        message1 = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test1', out=False, grouped_id=999)
        message2 = types.Message(id=2, peer_id=types.PeerUser(123), date=None, message='test2', out=False, grouped_id=999)
        
        event = Album.Event([message1, message2])
        event._client = MagicMock()
        event._client.forward_messages = AsyncMock(return_value='result')
        event.get_input_chat = AsyncMock(return_value='chat')
        
        result = await event.forward_to('destination')
        assert result == 'result'

    @pytest.mark.asyncio
    async def test_album_event_delete(self):
        from telethon.events.album import Album
        
        message1 = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test1', out=False, grouped_id=999)
        message2 = types.Message(id=2, peer_id=types.PeerUser(123), date=None, message='test2', out=False, grouped_id=999)
        
        event = Album.Event([message1, message2])
        event._client = MagicMock()
        event._client.delete_messages = AsyncMock(return_value='result')
        event.get_input_chat = AsyncMock(return_value='chat')
        
        result = await event.delete()
        assert result == 'result'

    @pytest.mark.asyncio
    async def test_album_event_mark_read(self):
        from telethon.events.album import Album
        
        message1 = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test1', out=False, grouped_id=999)
        message2 = types.Message(id=2, peer_id=types.PeerUser(123), date=None, message='test2', out=False, grouped_id=999)
        
        event = Album.Event([message1, message2])
        event._client = MagicMock()
        event._client.send_read_acknowledge = AsyncMock()
        event.get_input_chat = AsyncMock(return_value='chat')
        
        await event.mark_read()
        event._client.send_read_acknowledge.assert_called_once()

    @pytest.mark.asyncio
    async def test_album_event_pin(self):
        from telethon.events.album import Album
        
        message1 = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test1', out=False, grouped_id=999)
        message2 = types.Message(id=2, peer_id=types.PeerUser(123), date=None, message='test2', out=False, grouped_id=999)
        
        event = Album.Event([message1, message2])
        event._client = MagicMock()
        
        # Mock the pin method on messages[0]
        event.messages[0].pin = AsyncMock(return_value='result')
        
        result = await event.pin(notify=True)
        assert result == 'result'


class TestAlbumHack:
    @pytest.mark.asyncio
    async def test_album_hack_extend(self):
        from telethon.events.album import AlbumHack
        
        message1 = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test1', out=False, grouped_id=999)
        message2 = types.Message(id=2, peer_id=types.PeerUser(123), date=None, message='test2', out=False, grouped_id=999)
        
        event = events.Album.Event([message1])
        
        client = MagicMock()
        loop = MagicMock()
        loop.time.return_value = 10.0
        loop.create_task = lambda x: None
        client.loop = loop
        
        hack = AlbumHack(client, event)
        assert hack._due == 10.5
        
        # Extend should add messages and update due time
        new_messages = [message2]
        hack.extend(new_messages)
        assert len(event.messages) == 2
        assert hack._due == 10.5

    @pytest.mark.asyncio
    async def test_album_hack_deliver_event_success(self):
        from telethon.events.album import AlbumHack
        
        message = types.Message(id=1, peer_id=types.PeerUser(123), date=None, message='test', out=False, grouped_id=999)
        event = events.Album.Event([message])
        
        client = MagicMock()
        loop = MagicMock()
        loop.time.return_value = 10.0
        loop.create_task = lambda x: None
        client.loop = loop
        client._dispatch_event = AsyncMock()
        
        hack = AlbumHack(client, event)
        
        # Manually set due time to past to trigger delivery
        hack._due = 9.0
        
        await hack.deliver_event()
        client._dispatch_event.assert_called_once_with(event)


class TestEventsInitFull:
    def test_unregister_with_event_instance(self):
        @events.register(events.NewMessage())
        async def handler(event):
            pass
        
        result = events.unregister(handler, events.NewMessage)
        assert result > 0

    def test_unregister_without_event(self):
        @events.register(events.NewMessage)
        async def handler(event):
            pass
        
        result = events.unregister(handler)
        assert result > 0
