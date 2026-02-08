import pytest

from telethon import TelegramClient, events, types, utils


def get_client():
    return TelegramClient(None, 1, '1')


def get_user_456():
    return types.User(
        id=456,
        access_hash=789,
        first_name='User 123'
    )


def get_user_789():
    return types.User(
        id=789,
        access_hash=123,
        first_name='User 789'
    )


def get_peer_user(id):
    return types.PeerUser(id)


@pytest.mark.asyncio
async def test_get_input_users_no_action_message_no_entities():
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())

    assert await event.get_input_users() == []


@pytest.mark.asyncio
async def test_get_input_users_no_action_message():
    user = get_user_456()
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())
    event._entities[user.id] = user

    assert await event.get_input_users() == [utils.get_input_peer(user)]


@pytest.mark.asyncio
async def test_get_users_no_action_message_no_entities():
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())

    assert await event.get_users() == []


@pytest.mark.asyncio
async def test_get_users_no_action_message():
    user = get_user_456()
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())
    event._entities[user.id] = user

    assert await event.get_users() == [user]


def test_build_update_pinned_channel_messages_unpin():
    event = events.ChatAction.build(types.UpdatePinnedChannelMessages(
        channel_id=123,
        messages=[1, 2, 3],
        pinned=False,
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.unpin is True
    assert event._pin_ids == [1, 2, 3]


def test_build_update_pinned_channel_messages_pin_ignored():
    event = events.ChatAction.build(types.UpdatePinnedChannelMessages(
        channel_id=123,
        messages=[1, 2, 3],
        pinned=True,
        pts=1,
        pts_count=1
    ))
    assert event is None


def test_build_update_pinned_messages_unpin():
    event = events.ChatAction.build(types.UpdatePinnedMessages(
        peer=types.PeerChat(123),
        messages=[1, 2, 3],
        pinned=False,
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.unpin is True
    assert event._pin_ids == [1, 2, 3]


def test_build_update_pinned_messages_pin_ignored():
    event = events.ChatAction.build(types.UpdatePinnedMessages(
        peer=types.PeerChat(123),
        messages=[1, 2, 3],
        pinned=True,
        pts=1,
        pts_count=1
    ))
    assert event is None


def test_build_update_chat_participant_add():
    event = events.ChatAction.build(types.UpdateChatParticipantAdd(
        chat_id=123,
        user_id=456,
        inviter_id=789,
        version=1,
        date=0
    ))
    assert event is not None
    assert event.user_added is True
    assert event._user_ids == [456]
    assert event._added_by == 789


def test_build_update_chat_participant_add_no_inviter():
    event = events.ChatAction.build(types.UpdateChatParticipantAdd(
        chat_id=123,
        user_id=456,
        inviter_id=0,
        version=1,
        date=0
    ))
    assert event is not None
    assert event.user_joined is True
    assert event._user_ids == [456]


def test_build_update_chat_participant_delete():
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    assert event is not None
    assert event.user_left is True
    assert event._user_ids == [456]


def test_build_message_action_chat_joined_by_link():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatJoinedByLink(inviter_id=789)
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.user_joined is True


def test_build_message_action_chat_add_user_self():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatAddUser(users=[456])
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.user_joined is True
    assert event._user_ids == [456]


def test_build_message_action_chat_add_user_other():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(789),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatAddUser(users=[456])
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.user_added is True
    assert event._user_ids == [456]


def test_build_message_action_chat_delete_user():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(789),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatDeleteUser(user_id=456)
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.user_kicked is True
    assert event._user_ids == [456]


def test_build_message_action_chat_delete_user_no_from():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatDeleteUser(user_id=456)
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.user_left is True
    assert event._user_ids == [456]


def test_build_message_action_chat_delete_user_self():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatDeleteUser(user_id=456)
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.user_left is True
    assert event._user_ids == [456]


def test_build_message_action_chat_create():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatCreate(
                title='Test Chat',
                users=[456, 789]
            )
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.created is True
    assert event.new_title == 'Test Chat'
    assert set(event._user_ids) == {456, 789}


def test_build_message_action_channel_create():
    event = events.ChatAction.build(types.UpdateNewChannelMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChannel(123),
            date=0,
            action=types.MessageActionChannelCreate(
                title='Test Channel'
            )
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.created is True
    assert event.new_title == 'Test Channel'


def test_build_message_action_chat_edit_title():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatEditTitle(title='New Title')
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.new_title == 'New Title'


def test_build_message_action_chat_edit_photo():
    photo = types.Photo(
        id=1,
        access_hash=2,
        file_reference=b'ref',
        date=0,
        dc_id=1,
        sizes=[types.PhotoSizeEmpty(type='s')]
    )
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatEditPhoto(photo=photo)
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.new_photo is True
    assert event.photo == photo


def test_build_message_action_chat_delete_photo():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionChatDeletePhoto()
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.new_photo is True
    assert event.photo is None


def test_build_message_action_pin_message():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionPinMessage()
        ),
        pts=1,
        pts_count=1
    ))
    assert event is None


def test_build_message_action_pin_message_with_reply_to():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionPinMessage(),
            reply_to=types.MessageReplyHeader(reply_to_msg_id=42)
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.new_pin is True
    assert event._pin_ids == [42]


def test_build_message_action_game_score():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.MessageService(
            id=1,
            from_id=get_peer_user(456),
            peer_id=types.PeerChat(123),
            date=0,
            action=types.MessageActionGameScore(score=100, game_id=1)
        ),
        pts=1,
        pts_count=1
    ))
    assert event is not None
    assert event.new_score == 100


def test_build_update_channel_participant_add():
    event = events.ChatAction.build(types.UpdateChannelParticipant(
        channel_id=123,
        user_id=456,
        actor_id=789,
        date=0,
        qts=1,
        prev_participant=None,
        new_participant=types.ChannelParticipant(user_id=456, date=0)
    ))
    assert event is not None
    assert event.user_added is True
    assert event._user_ids == [456]
    assert event._added_by == 789


def test_build_update_channel_participant_remove():
    event = events.ChatAction.build(types.UpdateChannelParticipant(
        channel_id=123,
        user_id=456,
        actor_id=789,
        date=0,
        qts=1,
        prev_participant=types.ChannelParticipant(user_id=456, date=0),
        new_participant=None
    ))
    assert event is not None
    assert event.user_kicked is True
    assert event._user_ids == [456]
    assert event._kicked_by == 789


def test_build_update_channel_participant_both_ignored():
    event = events.ChatAction.build(types.UpdateChannelParticipant(
        channel_id=123,
        user_id=456,
        actor_id=789,
        date=0,
        qts=1,
        prev_participant=types.ChannelParticipant(user_id=456, date=0),
        new_participant=types.ChannelParticipant(user_id=456, date=0)
    ))
    assert event is None


def test_build_update_channel_participant_none_ignored():
    event = events.ChatAction.build(types.UpdateChannelParticipant(
        channel_id=123,
        user_id=456,
        actor_id=789,
        date=0,
        qts=1,
        prev_participant=None,
        new_participant=None
    ))
    assert event is None


def test_event_init_with_message_service():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg)
    assert event.action_message == msg
    assert event.action_message is not None


def test_event_init_without_message_service():
    event = events.ChatAction.Event(types.PeerChat(123))
    assert event.action_message is None


def test_event_init_with_photo():
    photo = types.Photo(
        id=1,
        access_hash=2,
        file_reference=b'ref',
        date=0,
        dc_id=1,
        sizes=[types.PhotoSizeEmpty(type='s')]
    )
    event = events.ChatAction.Event(types.PeerChat(123), new_photo=photo)
    assert event.new_photo is True
    assert event.photo == photo


def test_event_init_new_photo_none():
    event = events.ChatAction.Event(types.PeerChat(123), new_photo=None)
    assert event.new_photo is False


def test_event_init_new_photo_true():
    event = events.ChatAction.Event(types.PeerChat(123), new_photo=True)
    assert event.new_photo is True
    assert event.photo is None


def test_event_init_added_by_true():
    event = events.ChatAction.Event(types.PeerChat(123), added_by=True)
    assert event.user_joined is True
    assert event.user_added is False


def test_event_init_added_by_value():
    event = events.ChatAction.Event(types.PeerChat(123), added_by=789)
    assert event.user_added is True
    assert event._added_by == 789


def test_event_init_added_by_none():
    event = events.ChatAction.Event(types.PeerChat(123), added_by=None)
    assert event.user_joined is False
    assert event.user_added is False


def test_event_init_kicked_by_true():
    event = events.ChatAction.Event(types.PeerChat(123), kicked_by=True)
    assert event.user_left is True
    assert event.user_kicked is False


def test_event_init_kicked_by_equals_user():
    event = events.ChatAction.Event(types.PeerChat(123), kicked_by=456, users=456)
    assert event.user_left is True
    assert event.user_kicked is False


def test_event_init_kicked_by_value():
    event = events.ChatAction.Event(types.PeerChat(123), kicked_by=789)
    assert event.user_kicked is True
    assert event._kicked_by == 789


def test_event_init_kicked_by_none():
    event = events.ChatAction.Event(types.PeerChat(123), kicked_by=None)
    assert event.user_left is False
    assert event.user_kicked is False


def test_event_init_users_list():
    event = events.ChatAction.Event(types.PeerChat(123), users=[456, 789])
    assert event._user_ids == [456, 789]


def test_event_init_users_single():
    event = events.ChatAction.Event(types.PeerChat(123), users=456)
    assert event._user_ids == [456]


def test_event_init_users_none():
    event = events.ChatAction.Event(types.PeerChat(123), users=None)
    assert event._user_ids == []


def test_event_init_pin_ids():
    event = events.ChatAction.Event(types.PeerChat(123), pin_ids=[1, 2, 3])
    assert event.new_pin is True
    assert event._pin_ids == [1, 2, 3]


def test_event_init_pin_true():
    event = events.ChatAction.Event(types.PeerChat(123), pin_ids=[1], pin=True)
    assert event.unpin is False


def test_event_init_pin_false():
    event = events.ChatAction.Event(types.PeerChat(123), pin_ids=[1], pin=False)
    assert event.unpin is True


def test_event_init_created():
    event = events.ChatAction.Event(types.PeerChat(123), created=True)
    assert event.created is True


def test_event_init_new_title():
    event = events.ChatAction.Event(types.PeerChat(123), new_title='New Title')
    assert event.new_title == 'New Title'


def test_event_init_new_score():
    event = events.ChatAction.Event(types.PeerChat(123), new_score=100)
    assert event.new_score == 100


@pytest.mark.asyncio
async def test_set_client_with_action_message():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg)
    client = get_client()
    event._set_client(client)
    assert event._client == client


@pytest.mark.asyncio
async def test_set_client_without_action_message():
    event = events.ChatAction.Event(types.PeerChat(123))
    client = get_client()
    event._set_client(client)
    assert event._client == client


@pytest.mark.asyncio
async def test_respond():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg)
    event._set_client(get_client())

    send_message_called = False
    async def mock_send_message(*args, **kwargs):
        nonlocal send_message_called
        send_message_called = True
        return None

    async def mock_get_input_chat(*args, **kwargs):
        return types.InputPeerChat(chat_id=123)

    event._client.send_message = mock_send_message
    event.get_input_chat = mock_get_input_chat
    await event.respond('test')
    assert send_message_called


@pytest.mark.asyncio
async def test_reply_without_action_message():
    event = events.ChatAction.Event(types.PeerChat(123))
    event._set_client(get_client())

    send_message_called = False
    async def mock_send_message(*args, **kwargs):
        nonlocal send_message_called
        send_message_called = True
        assert 'reply_to' not in kwargs
        return None

    async def mock_get_input_chat(*args, **kwargs):
        return types.InputPeerChat(chat_id=123)

    event._client.send_message = mock_send_message
    event.get_input_chat = mock_get_input_chat
    await event.reply('test')
    assert send_message_called


@pytest.mark.asyncio
async def test_reply_with_action_message():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg)
    event._set_client(get_client())

    send_message_called = False
    async def mock_send_message(*args, **kwargs):
        nonlocal send_message_called
        send_message_called = True
        assert kwargs['reply_to'] == 1
        return None

    async def mock_get_input_chat(*args, **kwargs):
        return types.InputPeerChat(chat_id=123)

    event._client.send_message = mock_send_message
    event.get_input_chat = mock_get_input_chat
    await event.reply('test')
    assert send_message_called


@pytest.mark.asyncio
async def test_delete_without_action_message():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = await event.delete()
    assert result is None


@pytest.mark.asyncio
async def test_delete_with_action_message():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg)
    event._set_client(get_client())

    delete_called = False
    async def mock_delete_messages(*args, **kwargs):
        nonlocal delete_called
        delete_called = True
        return None

    async def mock_get_input_chat(*args, **kwargs):
        return types.InputPeerChat(chat_id=123)

    event._client.delete_messages = mock_delete_messages
    event.get_input_chat = mock_get_input_chat
    await event.delete()
    assert delete_called


@pytest.mark.asyncio
async def test_get_pinned_message_no_pin_ids():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = await event.get_pinned_message()
    assert result is None


@pytest.mark.asyncio
async def test_get_pinned_message_with_pinned_messages():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, pin_ids=[1])
    event._set_client(get_client())
    event._pinned_messages = [types.Message(id=1, peer_id=types.PeerChat(123))]

    result = await event.get_pinned_message()
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_pinned_messages_no_pin_ids():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = await event.get_pinned_messages()
    assert result is None


@pytest.mark.asyncio
async def test_get_pinned_messages_empty_list():
    event = events.ChatAction.Event(types.PeerChat(123), pin_ids=[])
    result = await event.get_pinned_messages()
    assert result == []


@pytest.mark.asyncio
async def test_get_pinned_messages_with_ids():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, pin_ids=[1])
    event._set_client(get_client())

    get_messages_called = False
    async def mock_get_messages(*args, **kwargs):
        nonlocal get_messages_called
        get_messages_called = True
        return [types.Message(id=1, peer_id=types.PeerChat(123))]

    async def mock_get_input_chat(*args, **kwargs):
        return types.InputPeerChat(chat_id=123)

    event._client.get_messages = mock_get_messages
    event.get_input_chat = mock_get_input_chat
    result = await event.get_pinned_messages()
    assert get_messages_called
    assert result is not None


def test_added_by_property_with_entity():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, added_by=456)
    event._entities[456] = user

    result = event.added_by
    assert result == user


def test_added_by_property_without_entity():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, added_by=456)

    result = event.added_by
    assert result == 456


def test_added_by_property_none():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.added_by
    assert result is None


@pytest.mark.asyncio
async def test_get_added_by_already_cached():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, added_by=456)
    event._set_client(get_client())
    event._added_by = user

    get_entity_called = False
    async def mock_get_entity(*args, **kwargs):
        nonlocal get_entity_called
        get_entity_called = True
        return None

    event._client.get_entity = mock_get_entity
    result = await event.get_added_by()
    assert not get_entity_called
    assert result == user


def test_kicked_by_property_with_entity():
    user = get_user_789()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, kicked_by=789)
    event._entities[789] = user

    result = event.kicked_by
    assert result == user


def test_kicked_by_property_without_entity():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, kicked_by=789)

    result = event.kicked_by
    assert result == 789


def test_kicked_by_property_none():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.kicked_by
    assert result is None


@pytest.mark.asyncio
async def test_get_kicked_by_already_cached():
    user = get_user_789()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, kicked_by=789)
    event._set_client(get_client())
    event._kicked_by = user

    get_entity_called = False
    async def mock_get_entity(*args, **kwargs):
        nonlocal get_entity_called
        get_entity_called = True
        return None

    event._client.get_entity = mock_get_entity
    result = await event.get_kicked_by()
    assert not get_entity_called
    assert result == user


def test_user_property():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._entities[456] = user

    result = event.user
    assert result == user


def test_user_property_empty():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.user
    assert result is None


@pytest.mark.asyncio
async def test_get_user():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._entities[456] = user

    result = await event.get_user()
    assert result == user


@pytest.mark.asyncio
async def test_get_user_via_get_users():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])

    get_users_called = False
    async def mock_get_users():
        nonlocal get_users_called
        get_users_called = True
        event._users = [get_user_456()]
        return event._users

    event.get_users = mock_get_users
    result = await event.get_user()
    assert get_users_called
    assert result is not None


def test_input_user_property():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._entities[456] = user
    event._input_users = [utils.get_input_peer(user)]

    result = event.input_user
    assert result == utils.get_input_peer(user)


def test_input_user_property_empty():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.input_user
    assert result is None


@pytest.mark.asyncio
async def test_get_input_user():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._entities[456] = user
    event._input_users = [utils.get_input_peer(user)]

    result = await event.get_input_user()
    assert result == utils.get_input_peer(user)


@pytest.mark.asyncio
async def test_get_input_user_via_get_input_users():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])

    get_input_users_called = False
    async def mock_get_input_users():
        nonlocal get_input_users_called
        get_input_users_called = True
        event._input_users = [utils.get_input_peer(get_user_456())]
        return event._input_users

    event.get_input_users = mock_get_input_users
    result = await event.get_input_user()
    assert get_input_users_called
    assert result is not None


def test_user_id_property():
    event = events.ChatAction.Event(types.PeerChat(123), users=[456])
    result = event.user_id
    assert result == 456


def test_user_id_property_empty():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.user_id
    assert result is None


def test_users_property_with_entities():
    user1 = get_user_456()
    user2 = get_user_789()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456, 789])
    event._entities[456] = user1
    event._entities[789] = user2

    result = event.users
    assert len(result) == 2
    assert user1 in result
    assert user2 in result


def test_users_property_without_entities():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456, 789])

    result = event.users
    assert result == []


def test_users_property_no_user_ids():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.users
    assert result == []


@pytest.mark.asyncio
async def test_get_users():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._entities[456] = user

    result = await event.get_users()
    assert len(result) == 1
    assert user in result


@pytest.mark.asyncio
async def test_get_users_no_user_ids():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = await event.get_users()
    assert result == []


@pytest.mark.asyncio
async def test_get_users_via_action_message():
    user1 = get_user_456()
    user2 = get_user_789()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456, 789])
    event._set_client(get_client())
    event._entities[456] = user1

    reload_called = False
    async def mock_reload():
        nonlocal reload_called
        reload_called = True

    event.action_message._reload_message = mock_reload
    result = await event.get_users()
    assert reload_called


def test_input_users_property_from_entities():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._entities[456] = user

    result = event.input_users
    assert len(result) == 1
    assert result[0] == utils.get_input_peer(user)


def test_input_users_property_no_user_ids():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.input_users
    assert result == []


def test_input_users_property_from_cache():
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._set_client(get_client())

    class MockEntity:
        def _as_input_peer(self):
            return types.InputPeerUser(user_id=456, access_hash=789)

    mock_cache = {456: MockEntity()}
    event._client._mb_entity_cache = mock_cache

    result = event.input_users
    assert len(result) == 1


def test_input_users_property_empty():
    event = events.ChatAction.Event(types.PeerChat(123), users=[456])
    result = event.input_users
    assert result == []


@pytest.mark.asyncio
async def test_get_input_users():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._entities[456] = user

    result = await event.get_input_users()
    assert len(result) == 1
    assert result[0] == utils.get_input_peer(user)


@pytest.mark.asyncio
async def test_get_input_users_no_user_ids():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = await event.get_input_users()
    assert result == []





def test_user_ids_property():
    event = events.ChatAction.Event(types.PeerChat(123), users=[456, 789])
    result = event.user_ids
    assert result == [456, 789]


def test_user_ids_property_empty():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.user_ids
    assert result is None


def test_build_update_new_message_not_message_service():
    event = events.ChatAction.build(types.UpdateNewMessage(
        message=types.Message(
            id=1,
            peer_id=types.PeerChat(123),
            date=0,
            message='test'
        ),
        pts=1,
        pts_count=1
    ))
    assert event is None


def test_build_update_new_channel_message_not_message_service():
    event = events.ChatAction.build(types.UpdateNewChannelMessage(
        message=types.Message(
            id=1,
            peer_id=types.PeerChannel(123),
            date=0,
            message='test'
        ),
        pts=1,
        pts_count=1
    ))
    assert event is None


def test_added_by_property_entity_already_user():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, added_by=user)

    result = event.added_by
    assert result == user


def test_kicked_by_property_entity_already_user():
    user = get_user_789()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, kicked_by=user)

    result = event.kicked_by
    assert result == user


def test_user_property_empty():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.user
    assert result is None


def test_input_user_property_empty():
    event = events.ChatAction.Event(types.PeerChat(123))
    result = event.input_user
    assert result is None


def test_users_property_already_initialized():
    user1 = get_user_456()
    user2 = get_user_789()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456, 789])
    event._users = [user1, user2]

    result = event.users
    assert len(result) == 2
    assert user1 in result
    assert user2 in result


def test_input_users_property_already_initialized():
    user = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456])
    event._input_users = [utils.get_input_peer(user)]

    result = event.input_users
    assert len(result) == 1
    assert result[0] == utils.get_input_peer(user)


def test_users_property_partial_entities():
    user1 = get_user_456()
    msg = types.MessageService(
        id=1,
        peer_id=types.PeerChat(123),
        date=0,
        action=types.MessageActionChatCreate(title='Test', users=[])
    )
    event = events.ChatAction.Event(msg, users=[456, 789])
    event._entities[456] = user1

    result = event.users
    assert len(result) == 1
    assert user1 in result
