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


class TestAuthenticationStep3:
    """Tests for Step 3: Complete DH Exchange."""

    @pytest.mark.asyncio
    async def test_step3_aes_block_size_mismatch(self):
        """Test Step 3 with AES block size mismatch."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # ServerDHParams with encrypted_answer not divisible by 16
        server_dh = ServerDHParamsOk(
            nonce=client_nonce,
            server_nonce=server_nonce,
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

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Create ServerDHInnerData with WRONG nonce
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner_wrong = ServerDHInnerData(
            nonce=client_nonce + 1,  # Wrong nonce
            server_nonce=server_nonce,
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
            nonce=client_nonce,
            server_nonce=server_nonce,
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

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Create ServerDHInnerData with WRONG server_nonce
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner_wrong = ServerDHInnerData(
            nonce=client_nonce,
            server_nonce=server_nonce + 1,  # Wrong server_nonce
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
            nonce=client_nonce,
            server_nonce=server_nonce,
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
    async def test_step3_invalid_response_type(self):
        """Test Step 3 with invalid response type."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=client_nonce,
            server_nonce=server_nonce,
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
            nonce=client_nonce,
            server_nonce=server_nonce,
            encrypted_answer=encrypted_answer
        )

        # Return wrong type in step 3
        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, {'wrong': 'type'}])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            # Mock auth key
                            mock_auth_key = MagicMock()
                            mock_auth_key.calc_new_nonce_hash = MagicMock(return_value=b'\x00' * 16)

                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(AssertionError, match='Step 3.1 answer was'):
                                        await do_authentication(mock_sender)


class TestAuthenticationDhGen:
    """Tests for DhGen responses in Step 3."""

    @pytest.mark.asyncio
    async def test_dh_gen_fail_invalid_nonce(self):
        """Test DhGenFail with invalid nonce."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=client_nonce,
            server_nonce=server_nonce,
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
            nonce=client_nonce,
            server_nonce=server_nonce,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenFail response with wrong nonce
        mock_auth_key = MagicMock()
        mock_auth_key.calc_new_nonce_hash = MagicMock(return_value=b'\x00' * 16)

        dh_gen_fail = DhGenFail(
            nonce=client_nonce + 1,  # Wrong nonce
            server_nonce=server_nonce,
            new_nonce_hash3=b'\x00' * 16
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_fail])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid.*nonce'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_dh_gen_fail_invalid_server_nonce(self):
        """Test DhGenFail with invalid server_nonce."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=client_nonce,
            server_nonce=server_nonce,
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
            nonce=client_nonce,
            server_nonce=server_nonce,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenFail response with wrong server_nonce
        mock_auth_key = MagicMock()
        mock_auth_key.calc_new_nonce_hash = MagicMock(return_value=b'\x00' * 16)

        dh_gen_fail = DhGenFail(
            nonce=client_nonce,
            server_nonce=server_nonce + 1,  # Wrong server_nonce
            new_nonce_hash3=b'\x00' * 16
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_fail])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid.*server nonce'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_dh_gen_retry_invalid_hash(self):
        """Test DhGenRetry with invalid hash."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=client_nonce,
            server_nonce=server_nonce,
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
            nonce=client_nonce,
            server_nonce=server_nonce,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenRetry response with wrong hash
        mock_auth_key = MagicMock()
        mock_auth_key.calc_new_nonce_hash = MagicMock(return_value=b'\x00' * 16)

        dh_gen_retry = DhGenRetry(
            nonce=client_nonce,
            server_nonce=server_nonce,
            new_nonce_hash2=b'\xff' * 16  # Wrong hash
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_retry])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid new nonce hash'):
                                        await do_authentication(mock_sender)

    @pytest.mark.asyncio
    async def test_dh_gen_fail_invalid_hash(self):
        """Test DhGenFail with invalid hash."""
        mock_sender = AsyncMock()

        client_nonce = int.from_bytes(b'\x01' * 16, 'big', signed=True)
        server_nonce = int.from_bytes(b'\x02' * 16, 'little', signed=True)

        res_pq = ResPQ(
            nonce=client_nonce,
            server_nonce=server_nonce,
            pq=int(15).to_bytes(8, 'big', signed=False),
            server_public_key_fingerprints=[123]
        )

        # Create ServerDHInnerData
        dh_prime = int.from_bytes(b'\xff' * 256, 'big', signed=False)
        g = 2
        g_a = pow(g, 3, dh_prime)
        dh_prime_bytes = rsa.get_byte_array(dh_prime)
        g_a_bytes = rsa.get_byte_array(g_a)

        server_dh_inner = ServerDHInnerData(
            nonce=client_nonce,
            server_nonce=server_nonce,
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
            nonce=client_nonce,
            server_nonce=server_nonce,
            encrypted_answer=encrypted_answer
        )

        # Create DhGenFail response with wrong hash
        mock_auth_key = MagicMock()
        mock_auth_key.calc_new_nonce_hash = MagicMock(return_value=b'\x00' * 16)

        dh_gen_fail = DhGenFail(
            nonce=client_nonce,
            server_nonce=server_nonce,
            new_nonce_hash3=b'\xff' * 16  # Wrong hash
        )

        mock_sender.send = AsyncMock(side_effect=[res_pq, server_dh, dh_gen_fail])

        key = b'\x00' * 32
        iv = b'\x00' * 16

        with mock.patch('telethon.network.authenticator.rsa.encrypt', return_value=b'\x00' * 256):
            with mock.patch('telethon.network.authenticator.rsa.get_byte_array', return_value=b'\x00' * 4):
                with mock.patch('telethon.network.authenticator.Factorization.factorize', return_value=(3, 5)):
                    with mock.patch('telethon.network.authenticator.helpers.generate_key_data_from_nonce', return_value=(key, iv)):
                        with mock.patch('telethon.network.authenticator.AES.decrypt_ige', return_value=decrypted_answer):
                            with mock.patch('telethon.network.authenticator.AuthKey', return_value=mock_auth_key):
                                with mock.patch('telethon.network.authenticator.AES.encrypt_ige', return_value=b'\x00' * 32):
                                    with pytest.raises(SecurityError, match='Step 3 invalid new nonce hash'):
                                        await do_authentication(mock_sender)
