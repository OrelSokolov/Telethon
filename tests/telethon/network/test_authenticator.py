"""
Tests for Authenticator Module - Full Coverage
Focused on testing all code paths in do_authentication function
"""
import pytest
import os
import struct
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch
from hashlib import sha1

from telethon.network.authenticator import do_authentication, get_int
from telethon.tl.types import (
    ResPQ, PQInnerData, ServerDHParamsFail, ServerDHParamsOk,
    ServerDHInnerData, ClientDHInnerData, DhGenOk, DhGenRetry, DhGenFail
)
from telethon.tl.functions import (
    ReqPqMultiRequest, ReqDHParamsRequest, SetClientDHParamsRequest
)
from telethon.errors import SecurityError
from telethon.crypto import rsa


# Fixture for predictable nonces
@pytest.fixture
def predictable_nonces():
    """Returns predictable client and server nonces for testing."""
    client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
    server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)
    new_nonce = int.from_bytes(b'\x03' * 32, 'little', signed=True)
    b_nonce = int.from_bytes(b'\x04' * 256, 'big', signed=False)
    return client_nonce, server_nonce, new_nonce, b_nonce


class TestGetInt:
    """Tests for get_int helper function."""

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


class TestAuthenticationStep1:
    """Tests for Step 1: PQ Request."""

    @pytest.mark.asyncio
    async def test_step1_invalid_nonce(self):
        """Test Step 1 with invalid nonce from server."""
        mock_sender = AsyncMock()

        # Client generates nonce
        client_nonce = int.from_bytes(os.urandom(16), 'big', signed=True)
        server_nonce = int.from_bytes(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f', 'little', signed=True)

        # Server returns different nonce
        res_pq = ResPQ(
            nonce=client_nonce + 1,  # Different nonce
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        mock_sender.send = AsyncMock(return_value=res_pq)

        with mock.patch('telethon.network.authenticator.os.urandom', return_value=client_nonce.to_bytes(16, 'big', signed=True)):
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


class TestAuthenticationStep2:
    """Tests for Step 2: DH Exchange."""

    @pytest.mark.asyncio
    async def test_step2_invalid_nonce_in_dh_params(self):
        """Test Step 2 with invalid nonce in ServerDHParams."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # ServerDHParams with wrong nonce
        server_dh = ServerDHParamsOk(
            nonce=client_nonce + 1,  # Wrong nonce
            server_nonce=server_nonce,
            encrypted_answer=b'\x00' * 256
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        # Patch os.urandom to return predictable nonce
        with mock.patch('telethon.network.authenticator.os.urandom', return_value=b'\x01' * 16):
            with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
                with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                    with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                        with pytest.raises(SecurityError, match='Step 2 invalid nonce'):
                            await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_invalid_server_nonce_in_dh_params(self):
        """Test Step 2 with invalid server_nonce in ServerDHParams."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # ServerDHParams with wrong server_nonce
        server_dh = ServerDHParamsOk(
            nonce=client_nonce,
            server_nonce=server_nonce + 1,  # Wrong server_nonce
            encrypted_answer=b'\x00' * 256
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh])

        # Patch os.urandom to return predictable nonce
        with mock.patch('telethon.network.authenticator.os.urandom', return_value=b'\x01' * 16):
            with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
                with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                    with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                        with pytest.raises(SecurityError, match='Step 2 invalid server nonce'):
                            await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_invalid_response_type(self):
        """Test Step 2 with invalid response type."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Return wrong type in step 2
        mock_sender.send = AsyncMock(side_effect=[res_pq, {'wrong': 'type'}])

        # Patch os.urandom to return predictable nonce
        with mock.patch('telethon.network.authenticator.os.urandom', return_value=b'\x01' * 16):
            with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
                with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                    with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                        with pytest.raises(AssertionError, match='Step 2.1 answer was'):
                            await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_server_dh_fail_invalid_hash(self):
        """Test Step 2 with ServerDHParamsFail and invalid new_nonce_hash."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)
        new_nonce = int.from_bytes(b'\x03' * 32, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # ServerDHParamsFail with wrong hash
        server_dh_fail = ServerDHParamsFail(
            nonce=client_nonce,
            server_nonce=server_nonce,
            new_nonce_hash=b'\xff' * 16  # Wrong hash
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh_fail])

        # Patch os.urandom to return predictable nonce and new_nonce
        with mock.patch('telethon.network.authenticator.os.urandom', side_effect=[b'\x01' * 16, b'\x03' * 32]):
            with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
                with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                    with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                        with pytest.raises(SecurityError, match='Step 2 invalid DH fail nonce'):
                            await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_step2_no_valid_key_all_attempts_fail(self):
        """Test Step 2 when all key attempts fail."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[]
        )

        mock_sender.send = AsyncMock(return_value=res_pq)

        # Patch os.urandom to return predictable nonce
        with mock.patch('telethon.network.authenticator.os.urandom', return_value=b'\x01' * 16):
            with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=None):
                with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                    with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                        with pytest.raises(SecurityError, match='Step 2 could not find a valid key'):
                            await do_authentication(mock_sender)



