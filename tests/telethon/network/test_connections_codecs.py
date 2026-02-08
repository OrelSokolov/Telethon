"""
Tests for Network Connection Codecs - Additional Coverage
Continuation of test_connections.py
"""
import pytest
import asyncio
import struct
import base64
from unittest import mock
from unittest.mock import AsyncMock, MagicMock
from zlib import crc32

from telethon.network.connection.connection import (
    Connection, PacketCodec, ObfuscatedConnection
)
from telethon.network.connection.http import (
    ConnectionHttp, HttpPacketCodec, SSL_PORT
)
from telethon.network.connection.tcpabridged import (
    ConnectionTcpAbridged, AbridgedPacketCodec
)
from telethon.network.connection.tcpfull import (
    ConnectionTcpFull, FullPacketCodec
)
from telethon.network.connection.tcpintermediate import (
    ConnectionTcpIntermediate, IntermediatePacketCodec,
    RandomizedIntermediatePacketCodec
)
from telethon.network.connection.tcpmtproxy import (
    MTProxyIO, TcpMTProxy, ConnectionTcpMTProxyAbridged,
    ConnectionTcpMTProxyIntermediate, ConnectionTcpMTProxyRandomizedIntermediate
)
from telethon.network.connection.tcpobfuscated import (
    ObfuscatedIO, ConnectionTcpObfuscated
)
from telethon.errors import InvalidChecksumError, InvalidBufferError


@pytest.fixture
def mock_loggers():
    """Mock loggers fixture."""
    return {
        'telethon.network.connection': MagicMock(),
        'telethon.network.connection.connection': MagicMock(),
        'telethon.network.connection.http': MagicMock(),
        'telethon.network.connection.tcpabridged': MagicMock(),
        'telethon.network.connection.tcpfull': MagicMock(),
        'telethon.network.connection.tcpintermediate': MagicMock(),
        'telethon.network.connection.tcpmtproxy': MagicMock(),
        'telethon.network.connection.tcpobfuscated': MagicMock(),
    }


@pytest.fixture
def mock_reader():
    """Mock reader for async operations."""
    reader = MagicMock()
    reader.readexactly = AsyncMock()
    reader.readline = AsyncMock()
    return reader


@pytest.fixture
def mock_writer():
    """Mock writer for async operations."""
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    writer.close = MagicMock()
    return writer


class TestHttpPacketCodec:
    """Tests for HTTP packet codec."""

    def test_http_encode_packet(self, mock_loggers):
        """Test encoding HTTP packet."""
        conn = ConnectionHttp('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = HttpPacketCodec(conn)
        data = b'\x00\x01\x02\x03'
        encoded = codec.encode_packet(data)

        assert b'POST /api HTTP/1.1' in encoded
        assert b'Host: 127.0.0.1:443' in encoded
        assert b'Content-Length: 4' in encoded
        assert data in encoded



    @pytest.mark.asyncio
    async def test_http_read_packet_no_content_length(self, mock_loggers):
        """Test reading HTTP packet that doesn't have content-length."""
        conn = ConnectionHttp('127.0.0.1', 8080, 1, loggers=mock_loggers)
        codec = HttpPacketCodec(conn)

        # Simulate HTTP response without content-length - will loop forever
        # Mock to return empty line to break the loop
        class MockReader:
            def __init__(self):
                self.call_count = 0

            async def readline(self):
                self.call_count += 1
                if self.call_count == 1:
                    return b'HTTP/1.1 200 OK\r\n'
                elif self.call_count == 2:
                    return b'Server: nginx\r\n'
                elif self.call_count == 3:
                    return b''  # Empty line to break loop
                return b'\r\n'

            async def readexactly(self, n):
                return b''

        reader_mock = MockReader()

        # Should raise IncompleteReadError when readline returns empty line
        with pytest.raises(asyncio.IncompleteReadError):
            await codec.read_packet(reader_mock)

    def test_http_port_constant(self):
        """Test SSL_PORT constant."""
        assert SSL_PORT == 443


class TestConnectionHttp:
    """Tests for HTTP connection."""

    @pytest.mark.asyncio
    async def test_http_connect_with_ssl(self, mock_loggers):
        """Test HTTP connection with SSL."""
        conn = ConnectionHttp('127.0.0.1', 443, 1, loggers=mock_loggers)

        with mock.patch.object(Connection, '_connect', new_callable=AsyncMock) as mock_connect:
            await conn.connect(timeout=10)
            mock_connect.assert_called_once_with(timeout=10, ssl=True)

    @pytest.mark.asyncio
    async def test_http_connect_without_ssl(self, mock_loggers):
        """Test HTTP connection without SSL."""
        conn = ConnectionHttp('127.0.0.1', 80, 1, loggers=mock_loggers)

        with mock.patch.object(Connection, '_connect', new_callable=AsyncMock) as mock_connect:
            await conn.connect(timeout=10)
            mock_connect.assert_called_once_with(timeout=10, ssl=False)


class TestAbridgedPacketCodec:
    """Tests for Abridged packet codec."""

    def test_abridged_encode_packet_small(self, mock_loggers):
        """Test encoding small packet (< 508 bytes)."""
        conn = ConnectionTcpAbridged('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = AbridgedPacketCodec(conn)

        data = b'\x00' * 20  # 20 bytes / 4 = 5
        encoded = codec.encode_packet(data)

        assert encoded[0] == 5
        assert encoded[1:] == data

    def test_abridged_encode_packet_large(self, mock_loggers):
        """Test encoding large packet (>= 508 bytes)."""
        conn = ConnectionTcpAbridged('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = AbridgedPacketCodec(conn)

        data = b'\x00' * 512  # 512 bytes / 4 = 128
        encoded = codec.encode_packet(data)

        assert encoded[0] == 0x7f
        length = struct.unpack('<i', encoded[1:4] + b'\x00')[0]
        assert length == 128
        assert encoded[4:] == data

    @pytest.mark.asyncio
    async def test_abridged_read_packet_small(self, mock_loggers):
        """Test reading small packet."""
        conn = ConnectionTcpAbridged('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = AbridgedPacketCodec(conn)

        length = 10
        data = b'\x00' * (length << 2)
        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[bytes([length]), data])

        result = await codec.read_packet(reader_mock)
        assert result == data

    @pytest.mark.asyncio
    async def test_abridged_read_packet_large(self, mock_loggers):
        """Test reading large packet."""
        conn = ConnectionTcpAbridged('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = AbridgedPacketCodec(conn)

        length = 150
        data = b'\x00' * (length << 2)
        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[
            bytes([0x7f]),
            (length).to_bytes(3, 'little'),
            data
        ])

        result = await codec.read_packet(reader_mock)
        assert result == data


class TestFullPacketCodec:
    """Tests for Full packet codec."""

    def test_full_encode_packet(self, mock_loggers):
        """Test encoding full packet."""
        conn = ConnectionTcpFull('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = FullPacketCodec(conn)

        data = b'\x00\x01\x02\x03'
        encoded = codec.encode_packet(data)

        # Length = len(data) + 12
        packet_len = struct.unpack('<i', encoded[:4])[0]
        assert packet_len == 16

        # Sequence number
        seq = struct.unpack('<i', encoded[4:8])[0]
        assert seq == 0

        # Checksum
        expected_crc = crc32(encoded[:12])
        actual_crc = struct.unpack('<I', encoded[12:16])[0]
        assert actual_crc == expected_crc

    def test_full_encode_packet_increment_counter(self, mock_loggers):
        """Test that send counter increments."""
        conn = ConnectionTcpFull('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = FullPacketCodec(conn)

        codec.encode_packet(b'test1')
        codec.encode_packet(b'test2')

        assert codec._send_counter == 2

    @pytest.mark.asyncio
    async def test_full_read_packet(self, mock_loggers):
        """Test reading full packet."""
        conn = ConnectionTcpFull('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = FullPacketCodec(conn)

        data = b'test'
        packet_len_seq = struct.pack('<ii', 12 + len(data), 0)
        packet = packet_len_seq + data
        checksum = struct.pack('<I', crc32(packet))

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[packet_len_seq, data + checksum])

        result = await codec.read_packet(reader_mock)
        assert result == data

    @pytest.mark.asyncio
    async def test_full_read_packet_invalid_checksum(self, mock_loggers):
        """Test reading packet with invalid checksum."""
        conn = ConnectionTcpFull('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = FullPacketCodec(conn)

        packet_len_seq = struct.pack('<ii', 16, 0)
        data = b'test'
        checksum = struct.pack('<I', 0xdeadbeef)  # Invalid checksum

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[packet_len_seq, data + checksum])

        with pytest.raises(InvalidChecksumError):
            await codec.read_packet(reader_mock)

    @pytest.mark.asyncio
    async def test_full_read_packet_negative_length(self, mock_loggers):
        """Test reading packet with negative length."""
        conn = ConnectionTcpFull('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = FullPacketCodec(conn)

        # Negative length as observed in issue #4042
        packet_len_seq = struct.pack('<ii', -429, -429)
        body = struct.pack('<i', -429)

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[packet_len_seq, body])

        with pytest.raises(InvalidBufferError):
            await codec.read_packet(reader_mock)

    @pytest.mark.asyncio
    async def test_full_read_packet_small_length(self, mock_loggers):
        """Test reading packet with length < 8."""
        conn = ConnectionTcpFull('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = FullPacketCodec(conn)

        packet_len_seq = struct.pack('<ii', 4, 0)

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[packet_len_seq])

        with pytest.raises(InvalidBufferError):
            await codec.read_packet(reader_mock)


class TestIntermediatePacketCodec:
    """Tests for Intermediate packet codec."""

    def test_intermediate_encode_packet(self, mock_loggers):
        """Test encoding intermediate packet."""
        conn = ConnectionTcpIntermediate('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = IntermediatePacketCodec(conn)

        data = b'test data'
        encoded = codec.encode_packet(data)

        length = struct.unpack('<i', encoded[:4])[0]
        assert length == len(data)
        assert encoded[4:] == data

    @pytest.mark.asyncio
    async def test_intermediate_read_packet(self, mock_loggers):
        """Test reading intermediate packet."""
        conn = ConnectionTcpIntermediate('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = IntermediatePacketCodec(conn)

        data = b'test data'
        length_bytes = struct.pack('<i', len(data))

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[length_bytes, data])

        result = await codec.read_packet(reader_mock)
        assert result == data


class TestRandomizedIntermediatePacketCodec:
    """Tests for RandomizedIntermediate packet codec."""

    def test_randomized_encode_packet(self, mock_loggers):
        """Test encoding randomized packet."""
        conn = ConnectionTcpIntermediate('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = RandomizedIntermediatePacketCodec(conn)

        data = b'test data'
        encoded = codec.encode_packet(data)

        # The encoded data should have length prefix + data + 0-3 padding bytes
        length = struct.unpack('<i', encoded[:4])[0]
        assert len(data) <= length <= len(data) + 3

        # Data (without padding) should be at the end
        pad_size = length - len(data)
        assert encoded[4:-pad_size if pad_size > 0 else None] == data

    @pytest.mark.asyncio
    async def test_randomized_read_packet(self, mock_loggers):
        """Test reading randomized packet."""
        conn = ConnectionTcpIntermediate('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = RandomizedIntermediatePacketCodec(conn)

        data = b'test'
        padding = b'\x00\x01'
        packet = data + padding
        length_bytes = struct.pack('<i', len(packet))

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[length_bytes, packet])

        result = await codec.read_packet(reader_mock)
        assert result == data  # Padding should be removed

    @pytest.mark.asyncio
    async def test_randomized_read_packet_no_padding(self, mock_loggers):
        """Test reading randomized packet with no padding."""
        conn = ConnectionTcpIntermediate('127.0.0.1', 443, 1, loggers=mock_loggers)
        codec = RandomizedIntermediatePacketCodec(conn)

        data = b'test\x00\x01\x02\x03'  # 8 bytes, aligned to 4
        length_bytes = struct.pack('<i', len(data))

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(side_effect=[length_bytes, data])

        result = await codec.read_packet(reader_mock)
        assert result == data


class TestMTProxyIO:
    """Tests for MTProxy IO operations."""

    def test_mtproxy_init_header_invalid_secret_length(self, mock_loggers):
        """Test MTProxy header with invalid secret length."""
        conn = ConnectionTcpMTProxyAbridged('127.0.0.1', 443, 1, loggers=mock_loggers, proxy=('127.0.0.1', 443, 'deadbeefdeadbeefdeadbeefdead'))

        # Secret must be 16 bytes - modify to be 15 bytes
        conn._secret = b'\xde\xad\xbe\xef\xde\xad\xbe\xef\xde\xad\xbe\xef\xde\xad'

        with pytest.raises(ValueError, match='MTProxy secret must be a hex-string representing 16 bytes'):
            MTProxyIO.init_header(conn._secret, 1, AbridgedPacketCodec)

    def test_mtproxy_init_header_dd_secret_wrong_codec(self, mock_loggers):
        """Test MTProxy header with DD secret but wrong codec."""
        # Create a proper DD secret (17 bytes starting with 0xDD)
        dd_secret = b'\xdd' + b'\x00' * 16

        # DD secret requires RandomizedIntermediate codec
        with pytest.raises(ValueError, match='Only RandomizedIntermediate can be used with dd-secrets'):
            MTProxyIO.init_header(dd_secret, 1, AbridgedPacketCodec)

    def test_mtproxy_init_header_dd_secret_correct_codec(self, mock_loggers):
        """Test MTProxy header with DD secret and correct codec."""
        # Create a proper DD secret (17 bytes starting with 0xDD)
        dd_secret = b'\xdd' + b'\x00' * 16

        # DD secret with RandomizedIntermediate should work
        header, encryptor, decryptor = MTProxyIO.init_header(dd_secret, 1, RandomizedIntermediatePacketCodec)

        assert len(header) == 64
        assert encryptor is not None
        assert decryptor is not None

    def test_mtproxy_readexactly(self, mock_loggers):
        """Test MTProxy readexactly."""
        conn = ConnectionTcpMTProxyAbridged('127.0.0.1', 443, 1, loggers=mock_loggers, proxy=('127.0.0.1', 443, 'deadbeefdeadbeefdeadbeefdeadbeef'))

        header, encryptor, decryptor = MTProxyIO.init_header(conn._secret, 1, AbridgedPacketCodec)

        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(return_value=b'encrypted')

        mtproxy_io = MagicMock()
        mtproxy_io._reader = reader_mock
        mtproxy_io._decrypt = MagicMock()
        mtproxy_io._decrypt.encrypt.return_value = b'decrypted'

        result = asyncio.run(MTProxyIO.readexactly(mtproxy_io, 10))
        assert result == b'decrypted'

    def test_mtproxy_write(self, mock_loggers):
        """Test MTProxy write."""
        conn = ConnectionTcpMTProxyAbridged('127.0.0.1', 443, 1, loggers=mock_loggers, proxy=('127.0.0.1', 443, 'deadbeefdeadbeefdeadbeefdeadbeef'))

        header, encryptor, decryptor = MTProxyIO.init_header(conn._secret, 1, AbridgedPacketCodec)

        # Create a proper mock writer
        writer_mock = MagicMock()
        writer_mock.write = MagicMock()

        mtproxy_io = MagicMock()
        mtproxy_io._writer = writer_mock
        mtproxy_io._encrypt = MagicMock()
        mtproxy_io._encrypt.encrypt.return_value = b'encrypted'

        MTProxyIO.write(mtproxy_io, b'test data')
        writer_mock.write.assert_called_once_with(b'encrypted')


class TestTcpMTProxy:
    """Tests for TCP MTProxy connection."""

    def test_mtproxy_init(self, mock_loggers):
        """Test MTProxy initialization."""
        proxy = ('127.0.0.1', 443, 'deadbeefdeadbeefdeadbeefdeadbeef')
        conn = ConnectionTcpMTProxyAbridged('127.0.0.1', 443, 1, loggers=mock_loggers, proxy=proxy)

        assert conn._secret is not None

    def test_mtproxy_no_proxy_info(self, mock_loggers):
        """Test MTProxy without proxy info."""
        with pytest.raises(ValueError, match='No proxy info specified'):
            TcpMTProxy.address_info(None)

    def test_mtproxy_address_info(self, mock_loggers):
        """Test getting MTProxy address info."""
        proxy = ('127.0.0.1', 443, 'secret')
        addr, port = TcpMTProxy.address_info(proxy)

        assert addr == '127.0.0.1'
        assert port == 443

    def test_mtproxy_normalize_secret_hex(self, mock_loggers):
        """Test normalizing hex secret."""
        secret = 'deadbeefdeadbeefdeadbeefdeadbeef'
        result = TcpMTProxy.normalize_secret(secret)

        assert len(result) == 16

    def test_mtproxy_normalize_secret_base64(self, mock_loggers):
        """Test normalizing base64 secret."""
        # 16 bytes in base64
        secret = 'AAAAAAAAAAAAAAAAAAAAAA=='
        result = TcpMTProxy.normalize_secret(secret)

        assert len(result) == 16

    def test_mtproxy_normalize_secret_with_ee_prefix(self, mock_loggers):
        """Test normalizing secret with ee prefix."""
        secret = 'eedeadbeefdeadbeefdeadbeefdeadbeef'
        result = TcpMTProxy.normalize_secret(secret)

        assert len(result) == 16
        assert not result.startswith(b'ee')

    def test_mtproxy_normalize_secret_with_dd_prefix(self, mock_loggers):
        """Test normalizing secret with dd prefix."""
        secret = 'dddeadbeefdeadbeefdeadbeefdeadbeef'
        result = TcpMTProxy.normalize_secret(secret)

        assert len(result) == 16


class TestObfuscatedIO:
    """Tests for Obfuscated IO operations."""

    def test_obfuscated_init_header(self, mock_loggers):
        """Test Obfuscated header initialization."""
        # Should reject headers starting with keywords
        # The code loops until it finds a valid random sequence
        header, encryptor, decryptor = ObfuscatedIO.init_header(AbridgedPacketCodec)

        assert len(header) == 64
        assert header[0] != 0xef
        assert header[:4] not in (b'PVrG', b'GET ', b'POST', b'\xee\xee\xee\xee')
        assert header[4:8] != b'\x00\x00\x00\x00'

    def test_obfuscated_init_header_keywords_validation(self, mock_loggers):
        """Test Obfuscated header validation with keywords."""
        # Should reject headers starting with keywords
        # The code loops until it finds a valid random sequence
        header, encryptor, decryptor = ObfuscatedIO.init_header(AbridgedPacketCodec)

        assert len(header) == 64
        assert header[0] != 0xef
        assert header[:4] not in (b'PVrG', b'GET ', b'POST', b'\xee\xee\xee\xee')
        assert header[4:8] != b'\x00\x00\x00\x00'

    def test_obfuscated_init_header_checks_byte_0(self, mock_loggers):
        """Test Obfuscated header validation checks first byte."""
        header, encryptor, decryptor = ObfuscatedIO.init_header(AbridgedPacketCodec)

        # The condition checks that byte 0 is not 0xef
        assert header[0] != 0xef

    def test_obfuscated_init_header_no_keywords(self, mock_loggers):
        """Test Obfuscated header validation for no keywords."""
        header, encryptor, decryptor = ObfuscatedIO.init_header(AbridgedPacketCodec)

        # The condition checks first 4 bytes are not in keywords
        assert header[:4] not in (b'PVrG', b'GET ', b'POST', b'\xee\xee\xee\xee')

    def test_obfuscated_init_header_not_four_zeros(self, mock_loggers):
        """Test Obfuscated header validation for not 4 zeros."""
        header, encryptor, decryptor = ObfuscatedIO.init_header(AbridgedPacketCodec)

        # The condition checks bytes 4-8 are not all zeros
        assert header[4:8] != b'\x00\x00\x00\x00'

    def test_obfuscated_init_header_multiple_attempts(self, mock_loggers):
        """Test Obfuscated header may need multiple attempts to avoid keywords."""
        # Call init multiple times - each should produce a valid header
        for _ in range(10):
            header, encryptor, decryptor = ObfuscatedIO.init_header(AbridgedPacketCodec)
            assert len(header) == 64
            assert header[0] != 0xef
            assert header[:4] not in (b'PVrG', b'GET ', b'POST', b'\xee\xee\xee\xee')
            assert header[4:8] != b'\x00\x00\x00\x00'

    @pytest.mark.asyncio
    async def test_obfuscated_io_init_and_write(self, mock_loggers, mock_reader, mock_writer):
        """Test ObfuscatedIO initialization and write."""
        conn = ConnectionTcpObfuscated('127.0.0.1', 443, 1, loggers=mock_loggers)

        # Set up mock reader and writer
        mock_reader.readexactly = AsyncMock(return_value=b'test')
        mock_writer.write = MagicMock()

        conn._reader = mock_reader
        conn._writer = mock_writer

        # Initialize ObfuscatedIO
        obf_io = ObfuscatedIO(conn)

        # Test write method (encrypts and writes to writer)
        obf_io.write(b'test data')

        # Write should have been called with encrypted data
        mock_writer.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_obfuscated_io_readexactly(self, mock_loggers, mock_reader):
        """Test ObfuscatedIO readexactly method."""
        conn = ConnectionTcpObfuscated('127.0.0.1', 443, 1, loggers=mock_loggers)

        # Set up mock reader
        mock_reader.readexactly = AsyncMock(return_value=b'response')

        conn._reader = mock_reader
        conn._writer = MagicMock()

        # Initialize ObfuscatedIO
        obf_io = ObfuscatedIO(conn)

        # Test readexactly - should decrypt after reading
        result = await obf_io.readexactly(8)
        mock_reader.readexactly.assert_called_once_with(8)
        assert result is not None





class TestPacketCodec:
    """Tests for PacketCodec base class."""

    def test_packet_codec_init(self, mock_loggers):
        """Test PacketCodec initialization."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)

        class TestCodec(PacketCodec):
            tag = None

            def encode_packet(self, data):
                return data

            async def read_packet(self, reader):
                return await reader.readexactly(4)

        codec = TestCodec(conn)
        assert codec._conn == conn
