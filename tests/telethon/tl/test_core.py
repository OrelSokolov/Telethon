import pytest
import struct
import gzip
import json
from io import BytesIO
from datetime import datetime, date, timedelta, timezone
from unittest.mock import MagicMock, Mock

from telethon.tl import TLObject, TLRequest
from telethon.tl.core import GzipPacked, MessageContainer, RpcResult, TLMessage
from telethon.tl.types import RpcError
from telethon.extensions import BinaryReader


class TestTLObject:
    def test_pretty_format_dict_no_indent(self):
        obj = {'_': 'Test', 'key': 'value', 'num': 123}
        result = TLObject.pretty_format(obj)
        assert 'Test(' in result
        assert 'key=' in result
        assert 'value' in result
        assert 'num=' in result

    def test_pretty_format_dict_with_indent(self):
        obj = {'_': 'Test', 'key': 'value', 'num': 123}
        result = TLObject.pretty_format(obj, indent=0)
        assert 'Test' in result
        assert 'key=' in result
        assert '\t' in result or 'key=' in result

    def test_pretty_format_dict_with_indent_empty(self):
        obj = {'_': 'Test'}
        result = TLObject.pretty_format(obj, indent=0)
        assert 'Test' in result

    def test_pretty_format_dict_with_indent_no_fields(self):
        obj = {'_': 'Test'}
        result = TLObject.pretty_format(obj, indent=1)
        assert 'Test' in result
        assert '(' in result
        assert ')' in result

    def test_pretty_format_dict_with_indent_empty_dict(self):
        obj = {}
        result = TLObject.pretty_format(obj, indent=1)
        assert 'dict' in result
        assert '(' in result
        assert ')' in result

    def test_pretty_format_iterable_with_indent(self):
        obj = [1, 2, 3]
        result = TLObject.pretty_format(obj, indent=0)
        assert '[' in result
        assert ']' in result
        assert '\t' in result or ',' in result

    def test_pretty_format_nested_dict_with_indent(self):
        obj = {'_': 'Test', 'nested': {'key': 'value'}}
        result = TLObject.pretty_format(obj, indent=1)
        assert 'Test' in result
        assert 'nested' in result

    def test_module_level_functions(self):
        # Test module-level functions directly
        import telethon.tl.tlobject

        # Test _datetime_to_timestamp
        dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        ts = telethon.tl.tlobject._datetime_to_timestamp(dt)
        assert isinstance(ts, int)

        # Test _json_default with bytes (should return base64 encoded string)
        result = telethon.tl.tlobject._json_default(b'test')
        assert isinstance(result, str)

        # Test _json_default with datetime (should return ISO format)
        dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        result = telethon.tl.tlobject._json_default(dt)
        assert '2020' in result

        # Test _json_default with other type (should return repr)
        result = telethon.tl.tlobject._json_default(42)
        assert '42' in result

    def test_pretty_format_tlobject_no_indent(self):
        class TestObj(TLObject):
            def to_dict(self):
                return {'_': 'TestObj', 'value': 42}

        obj = TestObj()
        result = TLObject.pretty_format(obj)
        assert 'TestObj' in result
        assert 'value=42' in result

    def test_pretty_format_string(self):
        result = TLObject.pretty_format("test string")
        assert repr("test string") in result

    def test_pretty_format_bytes(self):
        data = b'test bytes'
        result = TLObject.pretty_format(data)
        assert repr(data) in result

    def test_pretty_format_list(self):
        obj = [1, 2, 3]
        result = TLObject.pretty_format(obj)
        assert '[' in result
        assert ']' in result
        assert '1' in result
        assert '2' in result
        assert '3' in result

    def test_pretty_format_nested_dict(self):
        obj = {'_': 'Test', 'nested': {'key': 'value'}}
        result = TLObject.pretty_format(obj, indent=0)
        assert 'nested' in result

    def test_serialize_bytes_string(self):
        result = TLObject.serialize_bytes("hello")
        assert b'\x05hello' in result

    def test_serialize_bytes_bytes_short(self):
        data = b'short'
        result = TLObject.serialize_bytes(data)
        assert len(result) > len(data)

    def test_serialize_bytes_bytes_long(self):
        data = b'a' * 300
        result = TLObject.serialize_bytes(data)
        assert len(result) > len(data)
        assert result[0] == 254

    def test_serialize_bytes_long_padding_needed(self):
        data = b'a' * 257
        result = TLObject.serialize_bytes(data)
        assert len(result) > len(data)
        assert result[0] == 254

    def test_serialize_bytes_long_no_padding_needed(self):
        data = b'a' * 256
        result = TLObject.serialize_bytes(data)
        assert len(result) > len(data)
        assert result[0] == 254

    def test_serialize_bytes_invalid_type(self):
        with pytest.raises(TypeError):
            TLObject.serialize_bytes(123)

    def test_serialize_datetime_none(self):
        result = TLObject.serialize_datetime(None)
        assert result == b'\0\0\0\0'

    def test_serialize_datetime_datetime(self):
        dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        result = TLObject.serialize_datetime(dt)
        assert len(result) == 4

    def test_serialize_datetime_date(self):
        d = date(2020, 1, 1)
        result = TLObject.serialize_datetime(d)
        assert len(result) == 4

    def test_serialize_datetime_float(self):
        result = TLObject.serialize_datetime(1577836800.0)
        assert len(result) == 4

    def test_serialize_datetime_timedelta(self):
        result = TLObject.serialize_datetime(timedelta(days=1))
        assert len(result) == 4

    def test_serialize_datetime_invalid(self):
        with pytest.raises(TypeError):
            TLObject.serialize_datetime("invalid")

    def test_eq_same_type_same_dict(self):
        class TestObj(TLObject):
            def to_dict(self):
                return {'_': 'Test', 'value': 42}

        obj1 = TestObj()
        obj2 = TestObj()
        assert obj1 == obj2

    def test_eq_different_type(self):
        class TestObj1(TLObject):
            def to_dict(self):
                return {'_': 'Test', 'value': 42}

        class TestObj2(TLObject):
            def to_dict(self):
                return {'_': 'Test', 'value': 42}

        obj1 = TestObj1()
        obj2 = TestObj2()
        assert obj1 != obj2

    def test_ne_same_type_diff_dict(self):
        class TestObj(TLObject):
            def __init__(self, value):
                self.value = value

            def to_dict(self):
                return {'_': 'Test', 'value': self.value}

        obj1 = TestObj(42)
        obj2 = TestObj(43)
        assert obj1 != obj2

    def test_str(self):
        class TestObj(TLObject):
            def to_dict(self):
                return {'_': 'TestObj', 'value': 42}

        obj = TestObj()
        result = str(obj)
        assert 'TestObj' in result
        assert 'value=42' in result

    def test_stringify(self):
        class TestObj(TLObject):
            def to_dict(self):
                return {'_': 'TestObj', 'value': 42}

        obj = TestObj()
        result = obj.stringify()
        assert 'TestObj' in result
        assert 'value=42' in result

    def test_stringify_nested(self):
        class TestObj(TLObject):
            def to_dict(self):
                return {'_': 'TestObj', 'nested': {'key': 'value'}}

        obj = TestObj()
        result = obj.stringify()
        assert 'TestObj' in result
        assert 'nested' in result

    def test_to_json_without_fp(self):
        class TestObj(TLObject):
            def to_dict(self):
                return {'_': 'TestObj', 'value': 42, 'data': b'test', 'dt': datetime(2020, 1, 1, tzinfo=timezone.utc)}

        obj = TestObj()
        result = obj.to_json()
        json_data = json.loads(result)
        assert json_data['_'] == 'TestObj'
        assert json_data['value'] == 42
        assert 'data' in json_data
        assert 'dt' in json_data

    def test_to_json_with_fp(self):
        class TestObj(TLObject):
            def to_dict(self):
                return {'_': 'TestObj', 'value': 42}

        obj = TestObj()
        from unittest.mock import mock_open
        m = mock_open()
        with m('test.json', 'w') as f:
            obj.to_json(f)
        assert m().write.called

    def test_bytes_without_bytes_method(self):
        class TestObj(TLObject):
            def _bytes(self):
                raise AttributeError()

        obj = TestObj()
        with pytest.raises(TypeError) as exc_info:
            bytes(obj)
        assert 'TLObject was expected' in str(exc_info.value)

    def test__bytes_not_implemented(self):
        class TestObj(TLObject):
            pass

        obj = TestObj()
        with pytest.raises(NotImplementedError):
            obj._bytes()

    def test_from_reader_not_implemented(self):
        with pytest.raises(NotImplementedError):
            TLObject.from_reader(None)

    def test_to_dict_not_implemented(self):
        class TestObj(TLObject):
            pass

        obj = TestObj()
        with pytest.raises(NotImplementedError):
            obj.to_dict()


class TestTLRequest:
    def test_read_result(self):
        reader = MagicMock()
        result_obj = 'test_result'
        reader.tgread_object.return_value = result_obj

        result = TLRequest.read_result(reader)
        assert result == result_obj

    @pytest.mark.asyncio
    async def test_resolve(self):
        class TestReq(TLRequest):
            pass

        req = TestReq()
        result = await req.resolve(None, None)
        assert result is None


class TestGzipPacked:
    def test_init(self):
        data = b'test data'
        obj = GzipPacked(data)
        assert obj.data == data

    def test_gzip_if_smaller_content_related_small(self):
        data = b'small'
        result = GzipPacked.gzip_if_smaller(True, data)
        assert result == data

    def test_gzip_if_smaller_content_related_large(self):
        data = b'a' * 1000
        result = GzipPacked.gzip_if_smaller(True, data)
        assert len(result) < len(data)

    def test_gzip_if_smaller_not_content_related(self):
        data = b'a' * 1000
        result = GzipPacked.gzip_if_smaller(False, data)
        assert result == data

    def test_bytes(self):
        data = b'test data'
        obj = GzipPacked(data)
        result = bytes(obj)
        assert len(result) > 4

    def test_read(self):
        reader = MagicMock(spec=BinaryReader)
        reader.read_int = MagicMock(return_value=GzipPacked.CONSTRUCTOR_ID)
        test_data = b'test data'
        compressed = gzip.compress(test_data)
        reader.tgread_bytes = MagicMock(return_value=compressed)

        result = GzipPacked.read(reader)
        assert result == test_data

    def test_from_reader(self):
        test_data = b'test data'
        compressed = gzip.compress(test_data)
        reader = MagicMock(spec=BinaryReader)
        reader.tgread_bytes = MagicMock(return_value=compressed)

        result = GzipPacked.from_reader(reader)
        assert result.data == test_data

    def test_to_dict(self):
        data = b'test data'
        obj = GzipPacked(data)
        result = obj.to_dict()
        assert result['_'] == 'GzipPacked'
        assert result['data'] == data


class TestMessageContainer:
    def test_init(self):
        messages = [TLMessage(1, 0, 'test')]
        obj = MessageContainer(messages)
        assert obj.messages == messages

    def test_init_none_messages(self):
        obj = MessageContainer(None)
        assert obj.messages is None

    def test_max_size(self):
        assert hasattr(MessageContainer, 'MAXIMUM_SIZE')
        assert MessageContainer.MAXIMUM_SIZE > 0

    def test_max_length(self):
        assert hasattr(MessageContainer, 'MAXIMUM_LENGTH')
        assert MessageContainer.MAXIMUM_LENGTH > 0

    def test_to_dict(self):
        msg1 = TLMessage(1, 0, 'test1')
        msg2 = TLMessage(2, 1, 'test2')
        container = MessageContainer([msg1, msg2])
        result = container.to_dict()
        assert result['_'] == 'MessageContainer'
        assert len(result['messages']) == 2
        assert result['messages'][0]['msg_id'] == 1
        assert result['messages'][1]['msg_id'] == 2

    def test_to_dict_none_messages(self):
        container = MessageContainer(None)
        result = container.to_dict()
        assert result['_'] == 'MessageContainer'
        assert result['messages'] == []

    def test_to_dict_none_in_list(self):
        container = MessageContainer([None, TLMessage(1, 0, 'test')])
        result = container.to_dict()
        assert len(result['messages']) == 2
        assert result['messages'][0] is None

    def test_from_reader_single_message(self):
        reader = MagicMock(spec=BinaryReader)
        reader.read_int = MagicMock(side_effect=[1, 0, 0, 4])
        reader.read_long = MagicMock(return_value=1)
        reader.tell_position = MagicMock(return_value=0)
        reader.set_position = MagicMock()
        test_obj = 'test'
        reader.tgread_object = MagicMock(return_value=test_obj)

        result = MessageContainer.from_reader(reader)
        assert result.messages[0].msg_id == 1
        assert result.messages[0].seq_no == 0
        assert result.messages[0].obj == test_obj

    def test_from_reader_multiple_messages(self):
        reader = BinaryReader(b'')
        reader.read_int = MagicMock(side_effect=[2, 1, 0, 0, 4, 2, 1, 0, 4])
        reader.read_long = MagicMock(side_effect=[1, 2])
        reader.tell_position = MagicMock(return_value=0)
        reader.set_position = MagicMock()
        reader.tgread_object = MagicMock(return_value='test')

        result = MessageContainer.from_reader(reader)
        assert len(result.messages) == 2
        assert result.messages[0].msg_id == 1
        assert result.messages[1].msg_id == 2


class TestRpcResult:
    def test_init_with_body(self):
        obj = RpcResult(123, b'body', None)
        assert obj.req_msg_id == 123
        assert obj.body == b'body'
        assert obj.error is None

    def test_init_with_error(self):
        error = RpcError(400, 'error message')
        obj = RpcResult(123, None, error)
        assert obj.req_msg_id == 123
        assert obj.body is None
        assert obj.error == error

    def test_from_reader_with_error(self):
        reader = MagicMock(spec=BinaryReader)
        reader.read_long = MagicMock(return_value=123)
        reader.read_int = MagicMock(side_effect=[RpcError.CONSTRUCTOR_ID, 400])
        reader.tgread_string = MagicMock(return_value='test error')

        result = RpcResult.from_reader(reader)
        assert result.req_msg_id == 123
        assert result.error.error_code == 400
        assert result.error.error_message == 'test error'
        assert result.body is None

    def test_from_reader_with_gzip(self):
        reader = MagicMock(spec=BinaryReader)
        reader.read_long = MagicMock(return_value=123)
        reader.read_int = MagicMock(return_value=GzipPacked.CONSTRUCTOR_ID)
        test_data = b'test data'
        compressed = gzip.compress(test_data)
        reader.tgread_bytes = MagicMock(return_value=compressed)

        result = RpcResult.from_reader(reader)
        assert result.req_msg_id == 123
        assert result.body == test_data
        assert result.error is None

    def test_from_reader_with_regular_data(self):
        reader = MagicMock(spec=BinaryReader)
        reader.read_long = MagicMock(return_value=123)
        reader.read_int = MagicMock(return_value=0x12345678)
        test_data = b'regular data'
        reader.seek = MagicMock()
        reader.read = MagicMock(return_value=test_data)

        result = RpcResult.from_reader(reader)
        assert result.req_msg_id == 123
        assert result.body == test_data
        assert result.error is None
        reader.seek.assert_called_once_with(-4)

    def test_to_dict(self):
        obj = RpcResult(123, b'body', None)
        result = obj.to_dict()
        assert result['_'] == 'RpcResult'
        assert result['req_msg_id'] == 123
        assert result['body'] == b'body'
        assert result['error'] is None

    def test_to_dict_with_error(self):
        error = RpcError(400, 'error message')
        obj = RpcResult(123, None, error)
        result = obj.to_dict()
        assert result['error'] == error


class TestTLMessage:
    def test_init(self):
        msg = TLMessage(123, 5, 'test_obj')
        assert msg.msg_id == 123
        assert msg.seq_no == 5
        assert msg.obj == 'test_obj'

    def test_size_overhead_constant(self):
        assert TLMessage.SIZE_OVERHEAD == 12

    def test_to_dict(self):
        msg = TLMessage(123, 5, 'test_obj')
        result = msg.to_dict()
        assert result['_'] == 'TLMessage'
        assert result['msg_id'] == 123
        assert result['seq_no'] == 5
        assert result['obj'] == 'test_obj'
