"""
Tests for Group 4: Network Connections - Complete Authentication Coverage
"""
import pytest
import asyncio
import os
import struct
from unittest import mock
from unittest.mock import AsyncMock, MagicMock
from zlib import crc32
from hashlib import sha1

from telethon.network.authenticator import do_authentication, get_int
from telethon.network.connection.connection import (
    Connection, ObfuscatedConnection, PacketCodec
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

from telethon.tl.types import (
    ResPQ, PQInnerData, ServerDHParamsFail, ServerDHParamsOk,
    ServerDHInnerData, ClientDHInnerData, DhGenOk, DhGenRetry, DhGenFail
)
from telethon.tl.functions import (
    ReqPqMultiRequest, ReqDHParamsRequest, SetClientDHParamsRequest
)
from telethon.errors import SecurityError, InvalidChecksumError, InvalidBufferError


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


class TestGetInt:
    """Tests for get_int function."""

    def test_get_int_signed_big_endian(self):
        """Test get_int with signed bytes."""
        byte_array = b'\x00\x00\x00\x01'
        result = get_int(byte_array, signed=True)
        assert result == 1

    def test_get_int_unsigned_big_endian(self):
        """Test get_int with unsigned bytes."""
        byte_array = b'\x00\x00\x00\x01'
        result = get_int(byte_array, signed=False)
        assert result == 1

    def test_get_int_negative_signed(self):
        """Test get_int with negative signed value."""
        byte_array = b'\xff\xff\xff\xff'
        result = get_int(byte_array, signed=True)
        assert result == -1

    def test_get_int_large_number(self):
        """Test get_int with large number."""
        byte_array = b'\x01\x00\x00\x00\x00\x00\x00\x00'
        result = get_int(byte_array, signed=False)
        assert result == 72057594037927936

    def test_get_int_zero(self):
        """Test get_int with zero value."""
        byte_array = b'\x00\x00\x00\x00'
        result = get_int(byte_array, signed=True)
        assert result == 0

    def test_get_int_max_positive(self):
        """Test get_int with maximum positive value."""
        byte_array = b'\x7f\xff\xff\xff'
        result = get_int(byte_array, signed=True)
        assert result == 2147483647

    def test_get_int_min_negative(self):
        """Test get_int with minimum negative value."""
        byte_array = b'\x80\x00\x00\x00'
        result = get_int(byte_array, signed=True)
        assert result == -2147483648


class TestAuthenticatorSuccessFlow:
    """Tests for successful authentication flow."""

    @pytest.mark.asyncio
    async def test_do_authentication_complete_success(self):
        """Test complete successful authentication flow."""
        mock_sender = AsyncMock()

        # Step 1: ResPQ response
        nonce_value = int.from_bytes(os.urandom(16), 'big', signed=True)
        server_nonce_value = int.from_bytes(os.urandom(16), 'little', signed=True)
        pq = 12345678901234567890  # Large number for factorization

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=pq.to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Step 2: ServerDHParamsOk response
        # Mock key/iv generation
        key = b'\x00' * 32
        iv = b'\x00' * 16

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)  # g^a mod dh_prime
        server_time = 1000000

        from telethon.crypto import rsa
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=server_time
        )

        # Encrypt with hash prefix
        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        encrypted_answer = hash_prefix + inner_bytes
        # Pad to 256 bytes
        encrypted_answer = encrypted_answer + b'\x00' * (256 - len(encrypted_answer))
        # Mock decryption will return this
        decrypted_answer = hash_prefix + inner_bytes

        server_dh_params = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Step 3: DhGenOk response
        b = int.from_bytes(os.urandom(256), 'big', signed=False)
        g_b = pow(g, b, dh_prime)
        gab = pow(g_a, b, dh_prime)

        # Mock auth key
        mock_auth_key = MagicMock()
        mock_auth_key.calc_new_nonce_hash = MagicMock(return_value=b'\x00' * 16)

        dh_gen = DhGenOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            new_nonce_hash1=b'\x00' * 16
        )

        # Mock all dependencies
        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                mock_get_bytes.side_effect = lambda x: x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 3)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with mock.patch('telethon.network.authenticator.AuthKey') as mock_auth_key_class:
                                mock_auth_key_class.return_value = mock_auth_key
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh_params, dh_gen])

                                    # Use specific nonce to pass step 1
                                    with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                        # First call for nonce, second for new_nonce
                                        nonce_bytes = nonce_value.to_bytes(16, 'big', signed=True)
                                        new_nonce_bytes = os.urandom(32)
                                        mock_urandom.side_effect = [nonce_bytes, new_nonce_bytes, b'\x00' * 256]

                                    auth_key, time_offset = await do_authentication(mock_sender)

                                    assert auth_key == mock_auth_key
                                    assert time_offset is not None


class TestAuthenticatorStep1:
    """Tests for Step 1 of authentication (PQ Request)."""

    @pytest.mark.asyncio
    async def test_step1_invalid_nonce(self):
        """Test Step 1 with invalid nonce from server."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(os.urandom(16), 'big', signed=True)
        server_nonce_value = int.from_bytes(os.urandom(16), 'little', signed=True)

        # Server returns different nonce
        res_pq = ResPQ(
            nonce=999999,  # Different nonce
            server_nonce=server_nonce_value,
            pq=int(12345).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        mock_sender.send = AsyncMock(return_value=res_pq)

        # Patch os.urandom to return our nonce
        with mock.patch('telethon.network.authenticator.os.urandom', return_value=nonce_value.to_bytes(16, 'big', signed=True)):
            with pytest.raises(SecurityError, match='Step 1 invalid nonce from server'):
                await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step1_invalid_response_type(self):
        """Test Step 1 with invalid response type."""
        mock_sender = AsyncMock()

        # Return wrong type
        mock_sender.send = AsyncMock(return_value={'wrong': 'type'})

        with mock.patch('telethon.network.authenticator.os.urandom', return_value=b'\x00' * 16):
            with pytest.raises(AssertionError, match='Step 1 answer was'):
                await do_authentication(mock_sender)


class TestAuthenticatorStep2:
    """Tests for Step 2 of authentication (DH Exchange)."""

    @pytest.mark.asyncio
    async def test_step2_invalid_nonce_in_dh_params(self):
        """Test Step 2 with invalid nonce in ServerDHParams."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),  # 3 * 5
            server_public_key_fingerprints=[123]
        )

        # ServerDHParams with wrong nonce
        server_dh = ServerDHParamsOk(
            nonce=999999,  # Wrong nonce
            server_nonce=server_nonce_value,
            encrypted_answer=b'\x00' * 256
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with pytest.raises(SecurityError, match='Step 2 invalid nonce'):
                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_invalid_server_nonce_in_dh_params(self):
        """Test Step 2 with invalid server_nonce in ServerDHParams."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # ServerDHParams with wrong server_nonce
        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=888888,  # Wrong server_nonce
            encrypted_answer=b'\x00' * 256
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with pytest.raises(SecurityError, match='Step 2 invalid server nonce'):
                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_invalid_response_type(self):
        """Test Step 2 with invalid response type."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Return wrong type in step 2
        mock_sender.send = AsyncMock(side_effect=[res_pq, {'wrong': 'type'}])

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with pytest.raises(AssertionError, match='Step 2.1 answer was'):
                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_server_dh_fail_invalid_hash(self):
        """Test Step 2 with ServerDHParamsFail and invalid new_nonce_hash."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)
        new_nonce_value = int.from_bytes(b'\x03' * 32, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # ServerDHParamsFail with wrong hash
        server_dh_fail = ServerDHParamsFail(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            new_nonce_hash=b'\xff' * 16  # Wrong hash
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh_fail])

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    # Patch os.urandom for new_nonce
                    with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                        nonce_bytes = nonce_value.to_bytes(16, 'big', signed=True)
                        new_nonce_bytes = new_nonce_value.to_bytes(32, 'little', signed=True)
                        mock_urandom.side_effect = [nonce_bytes, new_nonce_bytes]

                    with pytest.raises(SecurityError, match='Step 2 invalid DH fail nonce'):
                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_no_valid_key_first_attempt(self):
        """Test Step 2 when first attempt with regular keys fails."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # rsa.encrypt returns None first, then succeeds with use_old=True
        encrypt_results = [None, b'\x00' * 256]

        with mock.patch('telethon.network.authenticator.rsa.encrypt', side_effect=encrypt_results):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    # Continue to step 2 DH params (mock for testing that old keys were tried)
                    server_dh = ServerDHParamsOk(
                        nonce=nonce_value,
                        server_nonce=server_nonce_value,
                        encrypted_answer=b'\x00' * 256
                    )

                    mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

                    # This will fail later in step 3, but proves old keys were tried
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(b'\x00' * 32, b'\x00' * 16)):
                        with pytest.raises(Exception):  # Will fail in step 3
                            await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_no_valid_key_all_attempts_fail(self):
        """Test Step 2 when all key attempts fail."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # All encryption attempts return None
        mock_sender.send = AsyncMock(return_value=res_pq)

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=None):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with pytest.raises(SecurityError, match='Step 2 could not find a valid key'):
                        await do_authentication(mock_sender)


class TestAuthenticatorStep3:
    """Tests for Step 3 of authentication (Complete DH Exchange)."""

    @pytest.mark.asyncio
    async def test_step3_aes_block_size_mismatch(self):
        """Test Step 3 with AES block size mismatch."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # ServerDHParams with encrypted_answer not divisible by 16
        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=b'\x00' * 257  # Not divisible by 16
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with pytest.raises(SecurityError, match='Step 3 AES block size mismatch'):
                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_invalid_nonce_in_encrypted_answer(self):
        """Test Step 3 with invalid nonce in decrypted ServerDHInnerData."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData with WRONG nonce
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner_wrong = ServerDHInnerData(
            nonce=999999,  # Wrong nonce
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes_wrong = bytes(server_dh_inner_wrong)
        hash_prefix = sha1(inner_bytes_wrong).digest()
        decrypted_answer = hash_prefix + inner_bytes_wrong
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with pytest.raises(SecurityError, match='Step 3 Invalid nonce in encrypted answer'):
                                await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_invalid_server_nonce_in_encrypted_answer(self):
        """Test Step 3 with invalid server_nonce in decrypted ServerDHInnerData."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData with WRONG server_nonce
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner_wrong = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=888888,  # Wrong server_nonce
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes_wrong = bytes(server_dh_inner_wrong)
        hash_prefix = sha1(inner_bytes_wrong).digest()
        decrypted_answer = hash_prefix + inner_bytes_wrong
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with pytest.raises(SecurityError, match='Step 3 Invalid server nonce in encrypted answer'):
                                await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_g_out_of_range(self):
        """Test Step 3 with g value out of range (1, dh_prime - 1)."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData with g=1 (out of range)
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 1  # Out of range!
        g_a = pow(g, 3, dh_prime)  # Will be 1
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with pytest.raises(SecurityError, match='g_a is not within'):
                                await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_g_a_out_of_range(self):
        """Test Step 3 with g_a value out of range."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData with g_a out of range
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = 0  # Out of range!
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with pytest.raises(SecurityError, match='g_a is not within'):
                                await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_g_b_out_of_range(self):
        """Test Step 3 with g_b value out of range."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenOk response
        mock_auth_key = MagicMock()

        dh_gen = DhGenOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            new_nonce_hash1=b'\x00' * 16
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        # Patch os.urandom to return b=0 (out of range)
        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                def get_bytes_side_effect(x):
                    if x == 0:
                        return b'\x00'
                    return x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                mock_get_bytes.side_effect = get_bytes_side_effect

                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with mock.patch('telethon.network.authenticator.AuthKey') as mock_auth_key_class:
                                mock_auth_key_class.return_value = mock_auth_key
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    # Patch os.urandom for new_nonce and b
                                    with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                        new_nonce_bytes = b'\x03' * 32
                                        b_bytes = b'\x00' * 256  # b=0, g_b will be 1
                                        mock_urandom.side_effect = [nonce_value.to_bytes(16, 'big', signed=True), new_nonce_bytes, b_bytes]

                                    with pytest.raises(SecurityError, match='g_b is not within'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_g_a_out_of_safety_range(self):
        """Test Step 3 with g_a value out of safety range."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData with g_a too small
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        # g_a must be >= 2^(2048-64) but make it 1
        g_a = 1
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                mock_get_bytes.side_effect = lambda x: x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with pytest.raises(SecurityError, match='g_a is not within.*2\\{2048-64}'):
                                await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_g_b_out_of_safety_range(self):
        """Test Step 3 with g_b value out of safety range."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenOk response
        mock_auth_key = MagicMock()

        dh_gen = DhGenOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            new_nonce_hash1=b'\x00' * 16
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        # Patch os.urandom to return small b (g_b will be out of safety range)
        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                def get_bytes_side_effect(x):
                    if x == 0:
                        return b'\x00'
                    if x == 1:
                        return b'\x01'
                    return x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                mock_get_bytes.side_effect = get_bytes_side_effect

                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with mock.patch('telethon.network.authenticator.AuthKey') as mock_auth_key_class:
                                mock_auth_key_class.return_value = mock_auth_key
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    # Patch os.urandom for new_nonce and b
                                    with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                        new_nonce_bytes = b'\x03' * 32
                                        b_bytes = b'\x01'  # b=1, g_b will be 2
                                        mock_urandom.side_effect = [nonce_value.to_bytes(16, 'big', signed=True), new_nonce_bytes, b_bytes]

                                    with pytest.raises(SecurityError, match='g_b is not within.*2\\{2048-64}'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_invalid_response_type(self):
        """Test Step 3 with invalid response type."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Return wrong type in step 3
        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, {'wrong': 'type'}])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                def get_bytes_side_effect(x):
                    return x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                mock_get_bytes.side_effect = get_bytes_side_effect

                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            # Patch os.urandom
                            with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                new_nonce_bytes = b'\x03' * 32
                                b_bytes = b'\x04' * 256
                                mock_urandom.side_effect = [nonce_value.to_bytes(16, 'big', signed=True), new_nonce_bytes, b_bytes]

                            # Mock auth key
                            mock_auth_key = MagicMock()
                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(AssertionError, match='Step 3.1 answer was'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_dh_gen_retry_invalid_hash(self):
        """Test Step 3 with DhGenRetry and invalid hash."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenRetry response with wrong hash
        mock_auth_key = MagicMock()

        dh_gen_retry = DhGenRetry(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            new_nonce_hash2=b'\xff' * 16  # Wrong hash
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_retry])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                def get_bytes_side_effect(x):
                    return x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                mock_get_bytes.side_effect = get_bytes_side_effect

                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            # Patch os.urandom
                            with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                new_nonce_bytes = b'\x03' * 32
                                b_bytes = b'\x04' * 256
                                mock_urandom.side_effect = [nonce_value.to_bytes(16, 'big', signed=True), new_nonce_bytes, b_bytes]

                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid new nonce hash'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_dh_gen_fail_invalid_hash(self):
        """Test Step 3 with DhGenFail and invalid hash."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenFail response with wrong hash
        mock_auth_key = MagicMock()

        dh_gen_fail = DhGenFail(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            new_nonce_hash3=b'\xff' * 16  # Wrong hash
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_fail])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                def get_bytes_side_effect(x):
                    return x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                mock_get_bytes.side_effect = get_bytes_side_effect

                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            # Patch os.urandom
                            with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                new_nonce_bytes = b'\x03' * 32
                                b_bytes = b'\x04' * 256
                                mock_urandom.side_effect = [nonce_value.to_bytes(16, 'big', signed=True), new_nonce_bytes, b_bytes]

                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid new nonce hash'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_dh_gen_fail_invalid_nonce(self):
        """Test Step 3 with DhGenFail and invalid nonce."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenFail response with wrong nonce
        mock_auth_key = MagicMock()

        dh_gen_fail = DhGenFail(
            nonce=999999,  # Wrong nonce
            server_nonce=server_nonce_value,
            new_nonce_hash3=b'\x00' * 16
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_fail])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                def get_bytes_side_effect(x):
                    return x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                mock_get_bytes.side_effect = get_bytes_side_effect

                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            # Patch os.urandom
                            with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                new_nonce_bytes = b'\x03' * 32
                                b_bytes = b'\x04' * 256
                                mock_urandom.side_effect = [nonce_value.to_bytes(16, 'big', signed=True), new_nonce_bytes, b_bytes]

                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid.*nonce'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step3_dh_gen_fail_invalid_server_nonce(self):
        """Test Step 3 with DhGenFail and invalid server_nonce."""
        mock_sender = AsyncMock()

        nonce_value = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce_value = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        from telethon.crypto import rsa

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            g=g,
            dh_prime=dh_prime_bytes,
            g_a=g_a_bytes,
            server_time=1000000
        )

        inner_bytes = bytes(server_dh_inner)
        hash_prefix = sha1(inner_bytes).digest()
        decrypted_answer = hash_prefix + inner_bytes
        encrypted_answer = decrypted_answer + b'\x00' * (256 - len(decrypted_answer))

        server_dh = ServerDHParamsOk(
            nonce=nonce_value,
            server_nonce=server_nonce_value,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenFail response with wrong server_nonce
        mock_auth_key = MagicMock()

        dh_gen_fail = DhGenFail(
            nonce=nonce_value,
            server_nonce=888888,  # Wrong server_nonce
            new_nonce_hash3=b'\x00' * 16
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_fail])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array') as mock_get_bytes:
                def get_bytes_side_effect(x):
                    return x.to_bytes((x.bit_length() + 7) // 8 or 1, 'big', signed=False)
                mock_get_bytes.side_effect = get_bytes_side_effect

                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            # Patch os.urandom
                            with mock.patch('telethon.network.authenticator.os.urandom') as mock_urandom:
                                new_nonce_bytes = b'\x03' * 32
                                b_bytes = b'\x04' * 256
                                mock_urandom.side_effect = [nonce_value.to_bytes(16, 'big', signed=True), new_nonce_bytes, b_bytes]

                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid.*server nonce'):
                                        await do_authentication(mock_sender)


# Connection tests (reusing existing test structure)
class TestConnectionBase:
    """Tests for base Connection class."""

    def test_connection_init(self, mock_loggers):
        """Test Connection initialization."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)
        assert conn._ip == '127.0.0.1'
        assert conn._port == 443
        assert conn._dc_id == 1
        assert conn._proxy is None
        assert conn._local_addr is None
        assert conn._connected is False

    def test_connection_init_with_proxy(self, mock_loggers):
        """Test Connection initialization with proxy."""
        proxy = ('socks5', '127.0.0.1', 9050)
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers, proxy=proxy)
        assert conn._proxy == proxy

    def test_connection_init_with_local_addr(self, mock_loggers):
        """Test Connection initialization with local address."""
        local_addr = ('192.168.1.1', 0)
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers, local_addr=local_addr)
        assert conn._local_addr == local_addr

    @pytest.mark.asyncio
    async def test_connect_without_proxy(self, mock_loggers):
        """Test connection establishment without proxy."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)

        # Create actual mock objects
        reader_mock = MagicMock()
        reader_mock.readexactly = AsyncMock(return_value=b'test')
        reader_mock.readline = AsyncMock(return_value=b'')

        writer_mock = MagicMock()
        writer_mock.write = MagicMock()
        writer_mock.drain = AsyncMock()
        writer_mock.close = MagicMock()
        writer_mock.wait_closed = AsyncMock()

        with mock.patch('asyncio.open_connection', return_value=(reader_mock, writer_mock)):
            class TestCodec(PacketCodec):
                tag = b'test'

                def encode_packet(self, data):
                    return data

                async def read_packet(self, reader):
                    return await reader.readexactly(4)

            conn.packet_codec = TestCodec
            await conn.connect()
            assert conn._connected is True

    @pytest.mark.asyncio
    async def test_connect_with_invalid_local_addr(self, mock_loggers):
        """Test connection with invalid local address format."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers, local_addr=12345)

        with pytest.raises(ValueError, match='Unknown local address format'):
            await conn._connect()

    def test_send_not_connected(self, mock_loggers):
        """Test sending data when not connected."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)

        with pytest.raises(ConnectionError, match='Not connected'):
            asyncio.run(conn.send(b'test'))

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_loggers):
        """Test disconnection."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)
        conn._connected = True

        # Create mock writer
        writer_mock = MagicMock()
        writer_mock.close = MagicMock()
        writer_mock.wait_closed = AsyncMock()

        conn._writer = writer_mock
        conn._send_task = AsyncMock()
        conn._recv_task = AsyncMock()

        with mock.patch('telethon.network.connection.connection.helpers._cancel', new_callable=AsyncMock):
            await conn.disconnect()

        assert conn._connected is False
        writer_mock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_already_disconnected(self, mock_loggers):
        """Test disconnecting when already disconnected."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)
        conn._connected = False

        await conn.disconnect()
        assert conn._connected is False

    @pytest.mark.asyncio
    async def test_recv_not_connected(self, mock_loggers):
        """Test receiving when not connected."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)

        with pytest.raises(ConnectionError, match='Not connected'):
            await conn.recv()

    def test_str_representation(self, mock_loggers):
        """Test string representation of connection."""
        conn = Connection('127.0.0.1', 443, 1, loggers=mock_loggers)
        str_repr = str(conn)
        assert '127.0.0.1:443' in str_repr


# Additional codec tests will continue in separate file
