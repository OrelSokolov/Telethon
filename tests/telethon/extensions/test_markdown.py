"""
Tests for `telethon.extensions.markdown`.
"""
import re
import warnings
from telethon.extensions import markdown
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityTextUrl,
    MessageEntityCode, MessageEntityPre, MessageEntityMentionName,
    MessageEntityStrike
)


def test_entity_edges():
    """
    Test that entities at the edges (start and end) don't crash.
    """
    text = 'Hello, world'
    entities = [MessageEntityBold(0, 5), MessageEntityBold(7, 5)]
    result = markdown.unparse(text, entities)
    assert result == '**Hello**, **world**'


def test_malformed_entities():
    """
    Test that malformed entity offsets from bad clients
    don't crash and produce the expected results.
    """
    text = '🏆Telegram Official Android Challenge is over🏆.'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = markdown.unparse(text, entities)
    assert result == "🏆[Telegram Official Android Challenge is over](https://example.com)🏆."


def test_trailing_malformed_entities():
    """
    Similar to `test_malformed_entities`, but for the edge
    case where the malformed entity offset is right at the end
    (note the lack of a trailing dot in the text string).
    """
    text = '🏆Telegram Official Android Challenge is over🏆'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = markdown.unparse(text, entities)
    assert result == "🏆[Telegram Official Android Challenge is over](https://example.com)🏆"


def test_entities_together():
    """
    Test that an entity followed immediately by a different one behaves well.
    """
    original = '**⚙️**__Settings__'
    stripped = '⚙️Settings'

    text, entities = markdown.parse(original)
    assert text == stripped
    assert entities == [MessageEntityBold(0, 2), MessageEntityItalic(2, 8)]

    text = markdown.unparse(text, entities)
    assert text == original


def test_nested_entities():
    """
    Test that an entity nested inside another one behaves well.
    """
    original = '**[Example](https://example.com)**'
    stripped = 'Example'

    text, entities = markdown.parse(original)
    assert text == stripped
    assert entities == [MessageEntityBold(0, 7), MessageEntityTextUrl(0, 7, url='https://example.com')]

    text = markdown.unparse(text, entities)
    assert text == original


def test_offset_at_emoji():
    """
    Tests that an entity starting at a emoji preserves the emoji.
    """
    text = 'Hi\n👉 See example'
    entities = [MessageEntityBold(0, 2), MessageEntityItalic(3, 2), MessageEntityBold(10, 7)]
    parsed = '**Hi**\n__👉__ See **example**'

    assert markdown.parse(parsed) == (text, entities)
    assert markdown.unparse(text, entities) == parsed


def test_parse_empty():
    """Test parsing empty markdown."""
    assert markdown.parse('') == ('', [])


def test_parse_text_only():
    """Test parsing text only without formatting."""
    assert markdown.parse('Hello world') == ('Hello world', [])


def test_parse_bold():
    """Test parsing bold with **."""
    text, entities = markdown.parse('**bold**')
    assert text == 'bold'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityBold)


def test_parse_italic():
    """Test parsing italic with __."""
    text, entities = markdown.parse('__italic__')
    assert text == 'italic'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityItalic)


def test_parse_strike():
    """Test parsing strikethrough with ~~."""
    text, entities = markdown.parse('~~strike~~')
    assert text == 'strike'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityStrike)


def test_parse_code():
    """Test parsing code with backticks."""
    text, entities = markdown.parse('`code`')
    assert text == 'code'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityCode)


def test_parse_pre():
    """Test parsing pre block with triple backticks."""
    text, entities = markdown.parse('```pre```')
    assert text == 'pre'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityPre)


def test_parse_url():
    """Test parsing URL in brackets."""
    text, entities = markdown.parse('[link](https://example.com)')
    assert text == 'link'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityTextUrl)
    assert entities[0].url == 'https://example.com'


def test_parse_custom_url_regex():
    """Test parsing with custom URL regex."""
    custom_re = re.compile(r'\[([^]]*?)\]\(([^)]*?)\)')
    text, entities = markdown.parse('[text](url)', url_re=custom_re)
    assert text == 'text'
    assert len(entities) == 1


def test_parse_empty_delimiters():
    """Test parsing with empty delimiters dict."""
    text, entities = markdown.parse('**bold**', delimiters={})
    assert text == '**bold**'
    assert len(entities) == 0


def test_parse_none_delimiters():
    """Test parsing with None delimiters."""
    text, entities = markdown.parse('**bold**', delimiters=None)
    assert text == 'bold'
    assert len(entities) == 1


def test_parse_custom_delimiters():
    """Test parsing with custom delimiters."""
    custom_delimiters = {'==': MessageEntityBold}
    text, entities = markdown.parse('==bold==', delimiters=custom_delimiters)
    assert text == 'bold'
    assert len(entities) == 1


def test_parse_no_matching_closing_delimiter():
    """Test when opening delimiter has no closing."""
    text, entities = markdown.parse('**bold')
    assert text == '**bold'
    assert len(entities) == 0


def test_parse_nested_delimiters():
    """Test that nested delimiters work."""
    text, entities = markdown.parse('**bold and __italic__ bold**')
    assert 'bold and' in text
    assert 'italic' in text


def test_parse_code_skips_inner():
    """Test that code blocks skip inner entities."""
    text, entities = markdown.parse('`**bold**`')
    assert text == '**bold**'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityCode)


def test_parse_pre_skips_inner():
    """Test that pre blocks skip inner entities."""
    text, entities = markdown.parse('```**bold**```')
    assert text == '**bold**'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityPre)


def test_unparse_empty():
    """Test unparsing empty text."""
    assert markdown.unparse('', []) == ''


def test_unparse_empty_entities():
    """Test unparsing with empty entities list."""
    assert markdown.unparse('Hello', []) == 'Hello'


def test_unparse_none_entities():
    """Test unparsing with None entities."""
    assert markdown.unparse('Hello', None) == 'Hello'


def test_unparse_bold():
    """Test unparsing bold entity."""
    text = 'Hello world'
    entities = [MessageEntityBold(0, 5)]
    result = markdown.unparse(text, entities)
    assert result == '**Hello** world'


def test_unparse_italic():
    """Test unparsing italic entity."""
    text = 'Hello world'
    entities = [MessageEntityItalic(6, 5)]
    result = markdown.unparse(text, entities)
    assert result == 'Hello __world__'


def test_unparse_strike():
    """Test unparsing strike entity."""
    text = 'Hello world'
    entities = [MessageEntityStrike(0, 5)]
    result = markdown.unparse(text, entities)
    assert result == '~~Hello~~ world'


def test_unparse_code():
    """Test unparsing code entity."""
    text = 'Hello world'
    entities = [MessageEntityCode(0, 5)]
    result = markdown.unparse(text, entities)
    assert result == '`Hello` world'


def test_unparse_pre():
    """Test unparsing pre entity."""
    text = 'code'
    entities = [MessageEntityPre(0, 4, '')]
    result = markdown.unparse(text, entities)
    assert result == '```code```'


def test_unparse_url():
    """Test unparsing TextUrl entity."""
    text = 'link'
    entities = [MessageEntityTextUrl(0, 4, 'https://example.com')]
    result = markdown.unparse(text, entities)
    assert result == '[link](https://example.com)'


def test_unparse_mention_name():
    """Test unparsing MentionName entity."""
    text = 'John'
    entities = [MessageEntityMentionName(0, 4, user_id=123)]
    result = markdown.unparse(text, entities)
    assert result == '[John](tg://user?id=123)'


def test_unparse_single_entity():
    """Test unparsing a single entity object."""
    text = 'bold'
    entities = MessageEntityBold(0, 4)
    result = markdown.unparse(text, entities)
    assert result == '**bold**'


def test_unparse_custom_delimiters():
    """Test unparsing with custom delimiters."""
    from telethon.tl.types import MessageEntityBold
    text = 'text'
    entities = [MessageEntityBold(0, 4)]
    custom_delimiters = {'==': MessageEntityBold}
    result = markdown.unparse(text, entities, delimiters=custom_delimiters)
    assert result == '==text=='


def test_unparse_none_delimiters():
    """Test unparsing with None delimiters."""
    text = 'text'
    entities = [MessageEntityBold(0, 4)]
    result = markdown.unparse(text, entities, delimiters=None)
    # None delimiters uses DEFAULT_DELIMITERS
    assert result == '**text**'


def test_unparse_empty_delimiters():
    """Test unparsing with empty delimiters dict."""
    text = 'text'
    entities = [MessageEntityBold(0, 4)]
    result = markdown.unparse(text, entities, delimiters={})
    # Empty dict returns original text
    assert result == text


def test_unparse_url_fmt_deprecation():
    """Test that url_fmt parameter shows deprecation warning."""
    text = 'link'
    entities = [MessageEntityTextUrl(0, 4, 'https://example.com')]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        markdown.unparse(text, entities, url_fmt='custom')
        assert len(w) == 1
        assert 'deprecated' in str(w[0].message).lower()


def test_parse_and_unparse_roundtrip():
    """Test that parse and unparse work together."""
    original = '**bold** __italic__ `code`'
    text, entities = markdown.parse(original)
    result = markdown.unparse(text, entities)
    assert result == original


def test_multiple_entities():
    """Test parsing multiple entities."""
    text, entities = markdown.parse('**bold** __italic__ ~~strike~~')
    assert len(entities) == 3
    assert entities[0].offset == 0
    assert entities[0].length == 4
    assert entities[1].offset == 5
    assert entities[1].length == 6
    assert entities[2].offset == 12
    assert entities[2].length == 6


def test_entity_at_end():
    """Test entity at the end of text."""
    text = 'Hello world'
    result = markdown.unparse(text, [MessageEntityBold(6, 5)])
    assert result == 'Hello **world**'
