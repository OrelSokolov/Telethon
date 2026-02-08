"""
Tests for `telethon.extensions.html`.
"""
from telethon.extensions import html
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityTextUrl,
    MessageEntityCode, MessageEntityPre, MessageEntityEmail,
    MessageEntityUrl, MessageEntityMentionName, MessageEntityCustomEmoji,
    MessageEntityUnderline, MessageEntityStrike, MessageEntityBlockquote
)


def test_entity_edges():
    """
    Test that entities at the edges (start and end) don't crash.
    """
    text = 'Hello, world'
    entities = [MessageEntityBold(0, 5), MessageEntityBold(7, 5)]
    result = html.unparse(text, entities)
    assert result == '<strong>Hello</strong>, <strong>world</strong>'


def test_malformed_entities():
    """
    Test that malformed entity offsets from bad clients
    don't crash and produce the expected results.
    """
    text = '🏆Telegram Official Android Challenge is over🏆.'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = html.unparse(text, entities)
    assert result == '🏆<a href="https://example.com">Telegram Official Android Challenge is over</a>🏆.'


def test_trailing_malformed_entities():
    """
    Similar to `test_malformed_entities`, but for the edge
    case where the malformed entity offset is right at the end
    (note the lack of a trailing dot in the text string).
    """
    text = '🏆Telegram Official Android Challenge is over🏆'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = html.unparse(text, entities)
    assert result == '🏆<a href="https://example.com">Telegram Official Android Challenge is over</a>🏆'


def test_entities_together():
    """
    Test that an entity followed immediately by a different one behaves well.
    """
    original = '<strong>⚙️</strong><em>Settings</em>'
    stripped = '⚙️Settings'

    text, entities = html.parse(original)
    assert text == stripped
    assert entities == [MessageEntityBold(0, 2), MessageEntityItalic(2, 8)]

    text = html.unparse(text, entities)
    assert text == original


def test_nested_entities():
    """
    Test that an entity nested inside another one behaves well.
    """
    original = '<a href="https://example.com"><strong>Example</strong></a>'
    original_entities = [MessageEntityTextUrl(0, 7, url='https://example.com'), MessageEntityBold(0, 7)]
    stripped = 'Example'

    text, entities = html.parse(original)
    assert text == stripped
    assert entities == original_entities

    text = html.unparse(text, entities)
    assert text == original


def test_offset_at_emoji():
    """
    Tests that an entity starting at a emoji preserves the emoji.
    """
    text = 'Hi\n👉 See example'
    entities = [MessageEntityBold(0, 2), MessageEntityItalic(3, 2), MessageEntityBold(10, 7)]
    parsed = '<strong>Hi</strong>\n<em>👉</em> See <strong>example</strong>'

    assert html.parse(parsed) == (text, entities)
    assert html.unparse(text, entities) == parsed


def test_parse_empty():
    """Test parsing empty HTML."""
    assert html.parse('') == ('', [])


def test_parse_text_only():
    """Test parsing text only without entities."""
    assert html.parse('Hello world') == ('Hello world', [])


def test_parse_bold():
    """Test parsing bold text."""
    text, entities = html.parse('<strong>bold</strong>')
    assert text == 'bold'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityBold)


def test_parse_italic():
    """Test parsing italic text."""
    text, entities = html.parse('<em>italic</em>')
    assert text == 'italic'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityItalic)


def test_parse_code():
    """Test parsing code."""
    text, entities = html.parse('<code>code</code>')
    assert text == 'code'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityCode)


def test_parse_pre():
    """Test parsing pre tag."""
    text, entities = html.parse('<pre>pre</pre>')
    assert text == 'pre'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityPre)
    assert entities[0].language == ''


def test_parse_pre_with_language():
    """Test parsing pre tag with language class."""
    text, entities = html.parse('<pre><code class="language-python">code</code></pre>')
    assert text == 'code'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityPre)
    assert entities[0].language == 'python'


def test_parse_email():
    """Test parsing email link."""
    text, entities = html.parse('<a href="mailto:test@example.com">email</a>')
    # HTML parser replaces text with the email address
    assert text == 'test@example.com'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityEmail)


def test_parse_url():
    """Test parsing URL link."""
    text, entities = html.parse('<a href="https://example.com">https://example.com</a>')
    assert text == 'https://example.com'
    assert len(entities) == 1
    # When href and text are same, it's still parsed as TextUrl
    assert isinstance(entities[0], MessageEntityTextUrl)


def test_parse_text_url():
    """Test parsing text with URL."""
    text, entities = html.parse('<a href="https://example.com">link text</a>')
    assert text == 'link text'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityTextUrl)
    assert entities[0].url == 'https://example.com'


def test_parse_mention_name():
    """Test parsing mention name."""
    text, entities = html.parse('<a href="tg://user?id=123">John</a>')
    # Note: The HTML parser doesn't treat tg://user?id=N specially
    # It's parsed as a regular TextUrl
    assert text == 'John'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityTextUrl)


def test_parse_custom_emoji():
    """Test parsing custom emoji."""
    text, entities = html.parse('<tg-emoji emoji-id="123">😀</tg-emoji>')
    assert text == '😀'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityCustomEmoji)
    assert entities[0].document_id == 123


def test_parse_custom_emoji_invalid_id():
    """Test parsing custom emoji with invalid id."""
    # When emoji-id is invalid (not an int), the tag is ignored
    text, entities = html.parse('<tg-emoji emoji-id="invalid">😀</tg-emoji>')
    # The tag is not recognized, so emoji text is parsed but no entity created
    assert text == '😀'
    assert len(entities) == 0


def test_parse_underline():
    """Test parsing underline."""
    text, entities = html.parse('<u>underline</u>')
    assert text == 'underline'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityUnderline)


def test_parse_strike():
    """Test parsing strikethrough."""
    text, entities = html.parse('<del>strike</del>')
    assert text == 'strike'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityStrike)


def test_parse_s_tag():
    """Test parsing s tag (strikethrough)."""
    text, entities = html.parse('<s>strike</s>')
    assert text == 'strike'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityStrike)


def test_parse_blockquote():
    """Test parsing blockquote."""
    text, entities = html.parse('<blockquote>quote</blockquote>')
    assert text == 'quote'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityBlockquote)


def test_parse_b_tag():
    """Test parsing b tag (bold)."""
    text, entities = html.parse('<b>bold</b>')
    assert text == 'bold'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityBold)


def test_parse_i_tag():
    """Test parsing i tag (italic)."""
    text, entities = html.parse('<i>italic</i>')
    assert text == 'italic'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityItalic)


def test_parse_a_without_href():
    """Test parsing a tag without href attribute."""
    # When a tag has no href, it returns early and doesn't create entity
    text, entities = html.parse('<a>link</a>')
    # Text is just the link content
    assert text == 'link'
    assert len(entities) == 0


def test_parse_pre_without_language():
    """Test parsing pre tag with code tag without language class."""
    text, entities = html.parse('<pre><code>code</code></pre>')
    assert text == 'code'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityPre)
    assert entities[0].language == ''


def test_parse_code_inside_pre():
    """Test parsing code inside pre without language."""
    text, entities = html.parse('<pre>text</pre>')
    assert text == 'text'
    assert len(entities) == 1
    assert isinstance(entities[0], MessageEntityPre)


def test_unparse_empty():
    """Test unparsing empty text."""
    assert html.unparse('', []) == ''


def test_unparse_text_only():
    """Test unparsing text without entities."""
    assert html.unparse('Hello', []) == 'Hello'


def test_unparse_bold():
    """Test unparsing bold entity."""
    text = 'Hello world'
    entities = [MessageEntityBold(0, 5)]
    result = html.unparse(text, entities)
    assert result == '<strong>Hello</strong> world'


def test_unparse_italic():
    """Test unparsing italic entity."""
    text = 'Hello world'
    entities = [MessageEntityItalic(6, 5)]
    result = html.unparse(text, entities)
    assert result == 'Hello <em>world</em>'


def test_unparse_code():
    """Test unparsing code entity."""
    text = 'Hello world'
    entities = [MessageEntityCode(0, 5)]
    result = html.unparse(text, entities)
    assert result == '<code>Hello</code> world'


def test_unparse_pre():
    """Test unparsing pre entity."""
    text = 'code'
    entities = [MessageEntityPre(0, 4, 'python')]
    result = html.unparse(text, entities)
    # Pre entities create a specific format with language class
    assert '<pre>' in result
    assert "language-python" in result
    assert "<code class=" in result
    assert 'code' in result
    assert '</code>' in result
    assert '</pre>' in result


def test_unparse_underline():
    """Test unparsing underline entity."""
    text = 'Hello world'
    entities = [MessageEntityUnderline(0, 5)]
    result = html.unparse(text, entities)
    assert result == '<u>Hello</u> world'


def test_unparse_strike():
    """Test unparsing strike entity."""
    text = 'Hello world'
    entities = [MessageEntityStrike(0, 5)]
    result = html.unparse(text, entities)
    assert result == '<del>Hello</del> world'


def test_unparse_blockquote():
    """Test unparsing blockquote entity."""
    text = 'quote'
    entities = [MessageEntityBlockquote(0, 5)]
    result = html.unparse(text, entities)
    assert result == '<blockquote>quote</blockquote>'


def test_unparse_email():
    """Test unparsing email entity."""
    text = 'test@example.com'
    entities = [MessageEntityEmail(0, 16)]
    result = html.unparse(text, entities)
    # Email entities create mailto link
    assert result == '<a href="mailto:test@example.com">test@example.com</a>'


def test_unparse_url():
    """Test unparsing URL entity."""
    text = 'https://example.com'
    entities = [MessageEntityUrl(0, 19)]
    result = html.unparse(text, entities)
    # URL entities create a link to URL
    assert result == '<a href="https://example.com">https://example.com</a>'


def test_unparse_mention_name():
    """Test unparsing mention name entity."""
    text = 'John'
    entities = [MessageEntityMentionName(0, 4, user_id=123)]
    result = html.unparse(text, entities)
    assert result == '<a href="tg://user?id=123">John</a>'


def test_unparse_custom_emoji():
    """Test unparsing custom emoji entity."""
    text = '😀'
    entities = [MessageEntityCustomEmoji(0, 2, document_id=123)]
    result = html.unparse(text, entities)
    assert result == '<tg-emoji emoji-id="123">😀</tg-emoji>'


def test_unparse_single_entity():
    """Test unparsing a single entity object."""
    text = 'bold'
    entities = MessageEntityBold(0, 4)
    result = html.unparse(text, entities)
    assert result == '<strong>bold</strong>'


def test_unparse_html_escape():
    """Test that HTML is properly escaped."""
    text = '<script>alert("xss")</script>'
    result = html.unparse(text, [])
    assert '<script>' not in result
    assert '&lt;script&gt;' in result


def test_parse_and_unparse_roundtrip():
    """Test that parse and unparse work together."""
    original = '<strong>bold</strong> <em>italic</em> <code>code</code>'
    text, entities = html.parse(original)
    result = html.unparse(text, entities)
    assert result == original


def test_multiple_entities():
    """Test parsing multiple entities."""
    text, entities = html.parse('<strong>bold</strong> <em>italic</em> <u>underline</u>')
    assert len(entities) == 3
    assert entities[0].offset == 0
    assert entities[0].length == 4
    assert entities[1].offset == 5
    assert entities[1].length == 6
    assert entities[2].offset == 12
    assert entities[2].length == 9


def test_extra_closing_tags():
    """Test parsing HTML with extra closing tags."""
    text, entities = html.parse('<strong>bold</strong></em>')
    # Extra closing tag is ignored
    assert text == 'bold'
    assert len(entities) == 1


def test_unparse_with_surrogate():
    """Test unparsing with surrogate characters (emoji)."""
    # This should trigger the within_surrogate loop in unparse
    text = '😀'
    from telethon.tl.types import MessageEntityBold
    entities = [MessageEntityBold(0, 2)]
    result = html.unparse(text, entities)
    assert result == '<strong>😀</strong>'
