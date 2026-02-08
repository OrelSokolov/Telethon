"""
Tests for `telethon.extensions.binaryreader`.
"""
import struct
import pytest
from datetime import datetime, timedelta, timezone

from telethon.extensions.binaryreader import BinaryReader
from telethon.errors import TypeNotFoundError


def test_init():
    """Test BinaryReader initialization."""
    data = b'\x01\x02\x03\x04'
    reader = BinaryReader(data)
    assert reader.stream == data
    assert reader.position == 0
    assert reader._last is None


def test_init_empty():
    """Test BinaryReader initialization with empty data."""
    reader = BinaryReader(b'')
    assert reader.stream == b''
    assert reader.position == 0


def test_init_none():
    """Test BinaryReader initialization with None."""
    reader = BinaryReader(None)
    assert reader.stream == b''


def test_read_byte():
    """Test reading a single byte."""
    data = b'\x01\xff\x7f\x80'
    reader = BinaryReader(data)
    assert reader.read_byte() == 0x01
    assert reader.read_byte() == 0xff
    assert reader.read_byte() == 0x7f
    assert reader.read_byte() == 0x80


def test_read_int_signed():
    """Test reading a signed integer."""
    data = struct.pack('<i', 123456789)
    reader = BinaryReader(data)
    assert reader.read_int(signed=True) == 123456789


def test_read_int_unsigned():
    """Test reading an unsigned integer."""
    data = struct.pack('<I', 123456789)
    reader = BinaryReader(data)
    assert reader.read_int(signed=False) == 123456789


def test_read_int_negative():
    """Test reading a negative signed integer."""
    data = struct.pack('<i', -123456789)
    reader = BinaryReader(data)
    assert reader.read_int(signed=True) == -123456789


def test_read_long_signed():
    """Test reading a signed long."""
    data = struct.pack('<q', 9223372036854775807)
    reader = BinaryReader(data)
    assert reader.read_long(signed=True) == 9223372036854775807


def test_read_long_unsigned():
    """Test reading an unsigned long."""
    data = struct.pack('<Q', 9223372036854775807)
    reader = BinaryReader(data)
    assert reader.read_long(signed=False) == 9223372036854775807


def test_read_long_negative():
    """Test reading a negative signed long."""
    data = struct.pack('<q', -9223372036854775807)
    reader = BinaryReader(data)
    assert reader.read_long(signed=True) == -9223372036854775807


def test_read_float():
    """Test reading a float."""
    data = struct.pack('<f', 3.14159)
    reader = BinaryReader(data)
    result = reader.read_float()
    assert abs(result - 3.14159) < 0.00001


def test_read_double():
    """Test reading a double."""
    data = struct.pack('<d', 3.141592653589793)
    reader = BinaryReader(data)
    result = reader.read_double()
    assert abs(result - 3.141592653589793) < 0.00001


def test_read_large_int_16_bits():
    """Test reading 16-bit integer."""
    data = struct.pack('<h', 1000)
    reader = BinaryReader(data)
    assert reader.read_large_int(16, signed=True) == 1000


def test_read_large_int_32_bits():
    """Test reading 32-bit integer."""
    data = struct.pack('<i', 2000000)
    reader = BinaryReader(data)
    assert reader.read_large_int(32, signed=True) == 2000000


def test_read_large_int_64_bits():
    """Test reading 64-bit integer."""
    data = struct.pack('<q', 9000000000)
    reader = BinaryReader(data)
    assert reader.read_large_int(64, signed=True) == 9000000000


def test_read_large_int_unsigned():
    """Test reading unsigned large int."""
    data = struct.pack('<Q', 18446744073709551615)
    reader = BinaryReader(data)
    assert reader.read_large_int(64, signed=False) == 18446744073709551615


def test_read_specified_length():
    """Test reading specified length."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    result = reader.read(5)
    assert result == b'Hello'
    assert reader.position == 5


def test_read_all_remaining():
    """Test reading all remaining bytes."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    reader.read(7)
    result = reader.read(-1)
    assert result == b'world!'
    assert reader.position == 13


def test_read_buffer_error():
    """Test BufferError when trying to read beyond data."""
    data = b'Hello'
    reader = BinaryReader(data)
    reader.read(3)
    with pytest.raises(BufferError, match='No more data left to read'):
        reader.read(10)


def test_get_bytes():
    """Test getting all bytes."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    assert reader.get_bytes() == b'Hello, world!'


def test_tgread_bytes_small():
    """Test reading small Telegram byte array."""
    data = b'\x05Hello\x00\x00\x00'
    reader = BinaryReader(data)
    result = reader.tgread_bytes()
    assert result == b'Hello'


def test_tgread_bytes_with_padding():
    """Test reading Telegram bytes with padding."""
    data = b'\x06Hello!\x00\x00'
    reader = BinaryReader(data)
    result = reader.tgread_bytes()
    assert result == b'Hello!'


def test_tgread_bytes_large():
    """Test reading large Telegram byte array (length >= 254)."""
    length = 300
    length_bytes = struct.pack('<I', length)[:3]  # Pack as 32-bit, take only 3 bytes
    data = b'\xfe' + length_bytes + b'A' * length
    padding = length % 4
    if padding > 0:
        padding = 4 - padding
        data += b'\x00' * padding
    reader = BinaryReader(data)
    result = reader.tgread_bytes()
    assert result == b'A' * length


def test_tgread_bytes_254():
    """Test reading Telegram bytes with exactly 254 bytes."""
    length = 254
    length_bytes = struct.pack('<I', length)[:3]
    data = b'\xfe' + length_bytes + b'A' * length
    padding = length % 4
    if padding > 0:
        padding = 4 - padding
        data += b'\x00' * padding
    reader = BinaryReader(data)
    result = reader.tgread_bytes()
    assert result == b'A' * length


def test_tgread_bytes_no_padding_needed():
    """Test reading Telegram bytes where length % 4 == 3."""
    data = b'\x03ABC'
    reader = BinaryReader(data)
    result = reader.tgread_bytes()
    assert result == b'ABC'


def test_tgread_string():
    """Test reading Telegram string."""
    data = b'\x05Hello\x00\x00\x00'
    reader = BinaryReader(data)
    result = reader.tgread_string()
    assert result == 'Hello'


def test_tgread_string_unicode():
    """Test reading Telegram string with unicode."""
    text = 'Привет, мир!'
    data = bytes([len(text.encode('utf-8'))]) + text.encode('utf-8') + b'\x00\x00\x00'
    reader = BinaryReader(data)
    result = reader.tgread_string()
    assert result == text


def test_tgread_string_with_invalid_utf8():
    """Test reading Telegram string with invalid UTF-8."""
    data = b'\x03\xff\xfe\xfd\x00\x00'
    reader = BinaryReader(data)
    result = reader.tgread_string()
    assert len(result) == 3


def test_tgread_bool_true():
    """Test reading Telegram boolean true."""
    data = struct.pack('<I', 0x997275b5)
    reader = BinaryReader(data)
    result = reader.tgread_bool()
    assert result is True


def test_tgread_bool_false():
    """Test reading Telegram boolean false."""
    data = struct.pack('<I', 0xbc799737)
    reader = BinaryReader(data)
    result = reader.tgread_bool()
    assert result is False


def test_tgread_bool_invalid():
    """Test reading invalid Telegram boolean."""
    data = struct.pack('<I', 0x12345678)
    reader = BinaryReader(data)
    with pytest.raises(RuntimeError, match='Invalid boolean code'):
        reader.tgread_bool()


def test_tgread_date():
    """Test reading Telegram date."""
    from datetime import datetime, timedelta, timezone
    import time
    
    epoch = datetime(*time.gmtime(0)[:6]).replace(tzinfo=timezone.utc)
    timestamp = 1234567890
    expected_date = epoch + timedelta(seconds=timestamp)
    
    data = struct.pack('<i', timestamp)
    reader = BinaryReader(data)
    result = reader.tgread_date()
    assert result == expected_date


def test_tgread_date_negative():
    """Test reading Telegram date with negative timestamp."""
    from datetime import datetime, timedelta, timezone
    import time
    
    epoch = datetime(*time.gmtime(0)[:6]).replace(tzinfo=timezone.utc)
    timestamp = -1000000
    expected_date = epoch + timedelta(seconds=timestamp)
    
    data = struct.pack('<i', timestamp)
    reader = BinaryReader(data)
    result = reader.tgread_date()
    assert result == expected_date


def test_tgread_object_bool_true():
    """Test reading Telegram object as bool true."""
    data = struct.pack('<I', 0x997275b5)
    reader = BinaryReader(data)
    result = reader.tgread_object()
    assert result is True


def test_tgread_object_bool_false():
    """Test reading Telegram object as bool false."""
    data = struct.pack('<I', 0xbc799737)
    reader = BinaryReader(data)
    result = reader.tgread_object()
    assert result is False


def test_tgread_object_vector():
    """Test reading Telegram vector."""
    vector_id = 0x1cb5c415
    count = 3
    data = struct.pack('<II', vector_id, count)
    data += struct.pack('<I', 0x997275b5)  # True
    data += struct.pack('<I', 0xbc799737)  # False
    data += struct.pack('<I', 0x997275b5)  # True
    
    reader = BinaryReader(data)
    result = reader.tgread_object()
    assert result == [True, False, True]


def test_tgread_object_invalid_constructor():
    """Test reading Telegram object with invalid constructor."""
    data = struct.pack('<I', 0x12345678)
    reader = BinaryReader(data)
    with pytest.raises(TypeNotFoundError):
        reader.tgread_object()


def test_tgread_vector_valid():
    """Test reading Telegram vector."""
    vector_id = 0x1cb5c415
    count = 3
    data = struct.pack('<I', vector_id)
    data += struct.pack('<i', count)
    data += struct.pack('<I', 0x997275b5)  # True
    data += struct.pack('<I', 0xbc799737)  # False
    data += struct.pack('<I', 0x997275b5)  # True
    
    reader = BinaryReader(data)
    result = reader.tgread_vector()
    assert result == [True, False, True]


def test_tgread_vector_invalid_constructor():
    """Test reading Telegram vector with invalid constructor."""
    data = struct.pack('<I', 0x12345678)
    reader = BinaryReader(data)
    with pytest.raises(RuntimeError, match='Invalid constructor code'):
        reader.tgread_vector()


def test_close():
    """Test closing the reader."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    reader.close()
    assert reader.stream == b''


def test_tell_position():
    """Test telling current position."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    assert reader.tell_position() == 0
    reader.read(5)
    assert reader.tell_position() == 5


def test_set_position():
    """Test setting position."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    reader.read(5)
    reader.set_position(2)
    assert reader.tell_position() == 2


def test_seek_positive():
    """Test seeking forward."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    reader.seek(5)
    assert reader.tell_position() == 5


def test_seek_negative():
    """Test seeking backward."""
    data = b'Hello, world!'
    reader = BinaryReader(data)
    reader.read(10)
    reader.seek(-3)
    assert reader.tell_position() == 7


def test_context_manager():
    """Test using BinaryReader as context manager."""
    data = b'Hello, world!'
    with BinaryReader(data) as reader:
        result = reader.read(5)
        assert result == b'Hello'
    assert reader.stream == b''


def test_last_read():
    """Test that _last stores the last read data."""
    data = b'HelloWorld'
    reader = BinaryReader(data)
    reader.read(5)
    assert reader._last == b'Hello'
    reader.read(5)
    assert reader._last == b'World'


def test_read_zero_length():
    """Test reading zero bytes."""
    data = b'Hello'
    reader = BinaryReader(data)
    result = reader.read(0)
    assert result == b''
    assert reader.position == 0


def test_large_int_negative_bits():
    """Test reading large negative int."""
    data = struct.pack('<i', -5000)
    reader = BinaryReader(data)
    assert reader.read_large_int(32, signed=True) == -5000


def test_tgread_bytes_padding_calculation():
    """Test padding calculation for various lengths."""
    for length in [1, 2, 3, 4, 5, 6, 7, 253, 254, 255, 256]:
        if length >= 254:
            length_bytes = struct.pack('<I', length)[:3]
            data = b'\xfe' + length_bytes + b'A' * length
            padding = length % 4
            if padding > 0:
                padding = 4 - padding
                data += b'\x00' * padding
        else:
            data = bytes([length]) + b'A' * length
            padding = (length + 1) % 4
            if padding > 0:
                padding = 4 - padding
                data += b'\x00' * padding
        
        reader = BinaryReader(data)
        result = reader.tgread_bytes()
        assert result == b'A' * length
