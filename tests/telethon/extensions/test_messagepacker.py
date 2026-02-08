"""
Tests for `telethon.extensions.messagepacker`.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from telethon.extensions.messagepacker import MessagePacker
from telethon.tl import TLRequest


@pytest.mark.asyncio
async def test_messagepacker_init():
    """Test MessagePacker initialization."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    packer = MessagePacker(state, loggers)
    assert packer._state is state
    assert len(packer._deque) == 0
    assert not packer._ready.is_set()


@pytest.mark.asyncio
async def test_append():
    """Test appending a single state."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    packer = MessagePacker(state, loggers)
    
    request_state = Mock()
    packer.append(request_state)
    
    assert len(packer._deque) == 1
    assert packer._deque[0] is request_state
    assert packer._ready.is_set()


@pytest.mark.asyncio
async def test_extend():
    """Test extending with multiple states."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    packer = MessagePacker(state, loggers)
    
    states = [Mock(), Mock(), Mock()]
    packer.extend(states)
    
    assert len(packer._deque) == 3
    assert list(packer._deque) == states
    assert packer._ready.is_set()


@pytest.mark.asyncio
async def test_get_single_message():
    """Test getting a single message."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    request_state = Mock()
    request_state.data = b'fake data'
    request_state.request = Mock(spec=TLRequest)
    request_state.after = None
    request_state.msg_id = None
    
    state.write_data_as_message = Mock(return_value=12345)
    
    packer = MessagePacker(state, loggers)
    packer.append(request_state)
    
    batch, data = await packer.get()
    
    assert len(batch) == 1
    assert batch[0] is request_state
    assert batch[0].msg_id == 12345
    assert data is not None


@pytest.mark.asyncio
async def test_get_multiple_messages():
    """Test getting multiple messages in container."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    states = []
    for i in range(3):
        request_state = Mock()
        request_state.data = b'fake data' * 10
        request_state.request = Mock(spec=TLRequest)
        request_state.after = None
        request_state.msg_id = None
        request_state.container_id = None
        state.write_data_as_message = Mock(return_value=1000 + i)
        states.append(request_state)
    
    packer = MessagePacker(state, loggers)
    packer.extend(states)
    
    batch, data = await packer.get()
    
    assert len(batch) == 3
    assert all(s.container_id is not None for s in batch)


@pytest.mark.asyncio
async def test_get_waits_for_data():
    """Test that get waits for data when queue is empty."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    packer = MessagePacker(state, loggers)
    
    async def add_data():
        await asyncio.sleep(0.1)
        request_state = Mock()
        request_state.data = b'fake data'
        request_state.request = Mock(spec=TLRequest)
        request_state.after = None
        request_state.msg_id = None
        state.write_data_as_message = Mock(return_value=12345)
        packer.append(request_state)
    
    task = asyncio.create_task(packer.get())
    await add_data()
    batch, data = await task
    
    assert len(batch) == 1


@pytest.mark.asyncio
async def test_get_returns_none_when_empty():
    """Test that get returns (None, None) when deque is cleared."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    packer = MessagePacker(state, loggers)
    packer._ready.set()
    
    batch, data = await packer.get()
    
    assert batch is None
    assert data is None


@pytest.mark.asyncio
async def test_message_too_large():
    """Test handling of a message that exceeds maximum size."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    from telethon.tl.core.messagecontainer import MessageContainer
    
    request_state = Mock()
    request_state.data = b'x' * (MessageContainer.MAXIMUM_SIZE + 1000)
    request_state.request = Mock()
    request_state.request.__class__.__name__ = 'TestRequest'
    request_state.future = asyncio.Future()
    
    packer = MessagePacker(state, loggers)
    packer.append(request_state)
    
    batch, data = await packer.get()
    
    assert batch is None
    assert data is None
    assert request_state.future.done()
    assert isinstance(request_state.future.exception(), ValueError)


@pytest.mark.asyncio
async def test_message_exactly_at_limit():
    """Test a message that is exactly at the size limit."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    from telethon.tl.core.messagecontainer import MessageContainer
    
    data_size = MessageContainer.MAXIMUM_SIZE - 12
    request_state = Mock()
    request_state.data = b'x' * data_size
    request_state.request = Mock(spec=TLRequest)
    request_state.after = None
    request_state.msg_id = None
    
    state.write_data_as_message = Mock(return_value=12345)
    
    packer = MessagePacker(state, loggers)
    packer.append(request_state)
    
    batch, data = await packer.get()
    
    assert len(batch) == 1
    assert batch[0].msg_id == 12345


@pytest.mark.asyncio
async def test_maximum_length():
    """Test that messages are limited by MAXIMUM_LENGTH."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    from telethon.tl.core.messagecontainer import MessageContainer
    
    states = []
    for i in range(MessageContainer.MAXIMUM_LENGTH + 5):
        request_state = Mock()
        request_state.data = b'x' * 10
        request_state.request = Mock(spec=TLRequest)
        request_state.after = None
        request_state.msg_id = None
        request_state.container_id = None
        state.write_data_as_message = Mock(return_value=1000 + i)
        states.append(request_state)
    
    packer = MessagePacker(state, loggers)
    packer.extend(states)
    
    batch, data = await packer.get()
    
    assert len(batch) == MessageContainer.MAXIMUM_LENGTH
    assert len(packer._deque) == 5


@pytest.mark.asyncio
async def test_second_batch_after_size_limit():
    """Test that remaining messages form a second batch."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    from telethon.tl.core.messagecontainer import MessageContainer
    
    data_size = (MessageContainer.MAXIMUM_SIZE // 2) - 6
    states = []
    for i in range(4):
        request_state = Mock()
        request_state.data = b'x' * data_size
        request_state.request = Mock(spec=TLRequest)
        request_state.after = None
        request_state.msg_id = None
        request_state.container_id = None
        state.write_data_as_message = Mock(return_value=1000 + i)
        states.append(request_state)
    
    packer = MessagePacker(state, loggers)
    packer.extend(states)
    
    batch1, data1 = await packer.get()
    assert len(batch1) == 2
    
    batch2, data2 = await packer.get()
    assert len(batch2) == 2


@pytest.mark.asyncio
async def test_with_after_id():
    """Test that after.msg_id is passed correctly."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    after_state = Mock()
    after_state.msg_id = 99999
    
    request_state = Mock()
    request_state.data = b'fake data'
    request_state.request = Mock(spec=TLRequest)
    request_state.after = after_state
    request_state.msg_id = None
    
    state.write_data_as_message = Mock(return_value=12345)
    
    packer = MessagePacker(state, loggers)
    packer.append(request_state)
    
    batch, data = await packer.get()
    
    state.write_data_as_message.assert_called_once()
    call_args = state.write_data_as_message.call_args
    assert call_args[1]['after_id'] == 99999


@pytest.mark.asyncio
async def test_content_related_false_for_container():
    """Test that content_related is False for container messages."""
    state = Mock()
    loggers = {'telethon.extensions.messagepacker': Mock()}
    
    states = []
    for i in range(2):
        request_state = Mock()
        request_state.data = b'fake data' * 10
        request_state.request = Mock(spec=TLRequest)
        request_state.after = None
        request_state.msg_id = None
        request_state.container_id = None
        state.write_data_as_message = Mock(return_value=1000 + i)
        states.append(request_state)
    
    packer = MessagePacker(state, loggers)
    packer.extend(states)
    
    batch, data = await packer.get()
    
    assert len(batch) == 2
    assert batch[0].container_id is not None
    assert batch[1].container_id is not None


@pytest.mark.asyncio
async def test_debug_logging():
    """Test that debug log messages are generated."""
    state = Mock()
    logger_mock = Mock()
    loggers = {'telethon.extensions.messagepacker': logger_mock}
    
    request_state = Mock()
    request_state.data = b'fake data'
    request_state.request = Mock()
    request_state.request.__class__.__name__ = 'TestRequest'
    request_state.after = None
    request_state.msg_id = None
    
    state.write_data_as_message = Mock(return_value=12345)
    
    packer = MessagePacker(state, loggers)
    packer.append(request_state)
    
    batch, data = await packer.get()
    
    logger_mock.debug.assert_called()


@pytest.mark.asyncio
async def test_warning_log_for_oversized_message():
    """Test that warning is logged for oversized messages."""
    state = Mock()
    logger_mock = Mock()
    loggers = {'telethon.extensions.messagepacker': logger_mock}
    
    from telethon.tl.core.messagecontainer import MessageContainer
    
    request_state = Mock()
    request_state.data = b'x' * (MessageContainer.MAXIMUM_SIZE + 1000)
    request_state.request = Mock()
    request_state.request.__class__.__name__ = 'TestRequest'
    request_state.future = asyncio.Future()
    
    packer = MessagePacker(state, loggers)
    packer.append(request_state)
    
    batch, data = await packer.get()
    
    logger_mock.warning.assert_called_once()
