"""Test font glyph coverage detection (get_font_coverage)."""
# std imports
import io
import os
import json
import time
import select

# 3rd party
import pytest

# local
from .conftest import IS_WINDOWS
from .accessories import TestTerminal, pty_test
from blessed._capabilities import FontCoverage
from blessed.terminal import (_FONT_QUERY_CHUNK_SIZE,
                              _RE_MINTTY_FONT_RESPONSE,
                              _RE_GLYPH_PROTOCOL_Q_RESPONSE,
                              _RE_GLYPH_PROTOCOL_S_RESPONSE)

pytestmark = pytest.mark.skipif(
    IS_WINDOWS, reason="PTY testing not supported on Windows")

# a CPR reply, the boundary that ends every round-trip; alone, it is a round-trip in
# which the terminal answered nothing
CPR = NO_REPLY = '\x1b[10;20R'
# a Glyph Protocol 's' verb reply, advertising support
PROBE = f'\x1b_25a1;s;fmt=glyf,colrv0\x1b\\{CPR}'
# separates the terminal queries a child wrote from the result it reports back
SENTINEL = '\x1e'
# 257 distinct codepoints, one more than a single query round-trip carries
LONG_TEXT = ''.join(chr(cp) for cp in
                    range(0x2500, 0x2500 + _FONT_QUERY_CHUNK_SIZE + 1))
# a result to exercise FontCoverage itself: A covered, B not, C by two sources,
# D unanswered, E never queried
SAMPLE = FontCoverage(sources={0x41: 'system', 0x42: '', 0x43: 'system,glossary'},
                      unknown={0x44: 'no reply'}, protocol='glyph')


def mintty(*codepoints, missing=()):
    """Build a mintty OSC 7771 reply for *codepoints*, those in *missing* uncovered."""
    # the reply is positional, repeating the query field for field: every codepoint
    # queried gets a ';', and only a covered one is named after it
    fields = ''.join(';' if cp in missing else f';{cp}' for cp in codepoints)
    return f'\x1b]7771;!{fields}\x07{CPR}'


def glyph(*pairs):
    """Build a Glyph Protocol 'q' verb reply of (codepoint, status) *pairs*."""
    return ''.join(f'\x1b_25a1;q;cp={cp:x};status={status}\x1b\\'
                   for cp, status in pairs) + CPR


def run(replies, *texts, name='run', parent=None, **kwargs):
    """Query a terminal answering *replies*, once per text, in a child process."""
    # returns (coverages, written): the result of each get_font_coverage call, and
    # the bytes the child wrote to its terminal.  Results cross the fork as JSON,
    # past SENTINEL, so that assertions may live here rather than in the child.
    def child(term):
        results = []
        term.ungetch(replies)
        for text in texts:
            coverage = term.get_font_coverage(text, **dict({'timeout': 0.01}, **kwargs))
            results.append([coverage.protocol, coverage.sources, coverage.unknown])
        return (SENTINEL + json.dumps(results)).encode()

    written, _, payload = pty_test(child, parent, test_name=name).partition(SENTINEL)
    return [FontCoverage(sources={int(cp): src for cp, src in sources.items()},
                         unknown={int(cp): why for cp, why in unknown.items()},
                         protocol=protocol)
            for protocol, sources, unknown in json.loads(payload)], written


@pytest.mark.parametrize('kwargs', [
    {'force_styling': True, 'is_a_tty': False},
    {'force_styling': False},
], ids=['not-a-tty', 'no-styling'])
def test_no_terminal_to_ask(kwargs):
    """An empty, falsey result when there is no styled tty to query."""
    term = TestTerminal(stream=io.StringIO(), **kwargs)
    coverage = term.get_font_coverage('abc', timeout=0.01)
    assert not coverage and coverage.protocol is None


@pytest.mark.parametrize('replies, text', [
    ('', 'A'),                     # not even a CPR comes back
    (NO_REPLY + NO_REPLY, 'A'),    # both protocols probed, both silent
    (mintty(65), ''),              # nothing asked about, nothing learned
], ids=['no-reply', 'both-silent', 'empty-text'])
def test_falsey_result(replies, text):
    """Nothing is known, and the result says so."""
    (coverage,), _ = run(replies, text, name='test_falsey_result')
    assert not coverage
    assert coverage.sources == {} and coverage.unknown == {}


def test_probes_are_not_repeated():
    """Once both protocols are known silent, nothing is ever sent again."""
    coverages, written = run(NO_REPLY + NO_REPLY, 'A', 'BCD',
                             name='test_probes_are_not_repeated')
    assert not any(coverages)
    assert written.count('\x1b]7771;?') == 1
    assert written.count('\x1b_25a1;s\x1b\\') == 1


@pytest.mark.parametrize('replies, text, sources', [
    # mintty names the covered codepoints, omitting the rest, and names no source of
    # its own, so 'system' stands for the font it answers about
    (mintty(65, 66, 67), 'ABC', {65: 'system', 66: 'system', 67: 'system'}),
    (mintty(65, 66, 67, missing=(66,)), 'ABC', {65: 'system', 66: '', 67: 'system'}),
    (mintty(65, 66, missing=(65, 66)), 'AB', {65: '', 66: ''}),
    (mintty(0x1f600), '\U0001f600', {0x1f600: 'system'}),
    # the Glyph Protocol names which sources cover each codepoint
    (NO_REPLY + PROBE + glyph((65, 'system'), (66, ''), (67, 'system,glossary')),
     'ABC', {65: 'system', 66: '', 67: 'system,glossary'}),
    (NO_REPLY + PROBE + glyph((0xe0a0, 'glossary')), '', {0xe0a0: 'glossary'}),
    # a zero status is success naming no source: uncovered, and not an error
    (NO_REPLY + PROBE + glyph((65, '0')), 'A', {65: ''}),
], ids=['mintty-all', 'mintty-partial', 'mintty-none', 'mintty-beyond-bmp',
        'glyph-sources', 'glyph-glossary-only', 'glyph-zero-status'])
def test_sources(replies, text, sources):
    """Coverage is reported per codepoint, keeping the source that covers it."""
    (coverage,), _ = run(replies, text, name='test_sources')
    assert coverage.sources == sources
    assert coverage.unknown == {}
    assert coverage.protocol == ('mintty' if replies.startswith('\x1b]') else 'glyph')


def test_mintty_covering_nothing_still_supports():
    """A reply of separators alone names no codepoint, yet proves the protocol."""
    # mintty answers field for field, so a font covering none of what was asked
    # replies with the separators and nothing else, ';' for a single codepoint
    (coverage,), _ = run(mintty(0x25a1, missing=(0x25a1,)), '\u25a1',
                         name='test_mintty_covering_nothing_still_supports')
    assert coverage.protocol == 'mintty' and coverage.supported
    assert coverage.uncovered == {0x25a1} and coverage.unknown == {}


@pytest.mark.parametrize('probe', [
    PROBE,                              # formats advertised
    f'\x1b_25a1;s;fmt=\x1b\\{CPR}',     # none advertised
    f'\x1b_25a1;s;\x1b\\{CPR}',         # no key=value pair at all
], ids=['formats', 'empty-fmt', 'valueless'])
def test_glyph_probe_variants(probe):
    """Any 's' reply is support: the 'q' verb does not depend on 'fmt'."""
    (coverage,), _ = run(NO_REPLY + probe + glyph((65, 'system')), 'A',
                         name='test_glyph_probe_variants')
    assert coverage.protocol == 'glyph' and coverage.covers('A')


@pytest.mark.parametrize('replies, text, written', [
    # each distinct codepoint named once, in decimal, ascending
    (mintty(65, 66), 'BABA', '\x1b]7771;?;65;66\x07'),
    # one APC per codepoint, in hex
    (NO_REPLY + PROBE + glyph((65, 'system'), (0xe0a0, 'system')), 'A\ue0a0',
     '\x1b_25a1;q;cp=41\x1b\\\x1b_25a1;q;cp=e0a0\x1b\\'),
], ids=['mintty', 'glyph'])
def test_query_shape(replies, text, written):
    """The query names the codepoints in the form each protocol expects."""
    assert written in run(replies, text, name='test_query_shape')[1]


@pytest.mark.parametrize('reply, unknown', [
    # an error reply names its reason, and leaves the batch otherwise unharmed ...
    ('\x1b_25a1;q;cp=41;status=2;reason=out_of_namespace\x1b\\'
     '\x1b_25a1;q;cp=42;status=system\x1b\\' + CPR, {65: 'out_of_namespace'}),
    # ... or falls back to naming its status
    ('\x1b_25a1;q;cp=41;status=7\x1b\\'
     '\x1b_25a1;q;cp=42;status=system\x1b\\' + CPR, {65: 'status=7'}),
    # no reply for this codepoint at all
    (glyph((66, 'system')), {65: 'no reply'}),
    # no reply to the whole query
    (NO_REPLY, {65: 'no reply', 66: 'no reply'}),
], ids=['error-reason', 'error-status', 'missing-one', 'missing-all'])
def test_unknown(reply, unknown):
    """An unanswered codepoint is neither covered nor uncovered."""
    (coverage,), _ = run(NO_REPLY + PROBE + reply, 'AB', name='test_unknown')
    assert coverage.supported is True
    assert coverage.unknown == unknown
    assert not set(unknown) & (coverage.covered | coverage.uncovered)


def test_unknown_is_not_asked_again():
    """A codepoint the terminal refused is not re-queried without force."""
    error = '\x1b_25a1;q;cp=41;status=1;reason=malformed\x1b\\' + CPR
    coverages, written = run(NO_REPLY + PROBE + error, 'A', 'A',
                             name='test_unknown_is_not_asked_again')
    assert all(coverage.unknown == {65: 'malformed'} for coverage in coverages)
    assert written.count('\x1b_25a1;q;cp=41\x1b\\') == 1


@pytest.mark.parametrize('answered', [True, False], ids=['answered', 'unanswered'])
def test_chunking(answered):
    """257 codepoints are asked for in a chunk of 256 and a chunk of one."""
    first = [ord(char) for char in LONG_TEXT[:_FONT_QUERY_CHUNK_SIZE]]
    last = ord(LONG_TEXT[-1])
    (coverage,), _ = run(mintty(*first) + (mintty(last) if answered else NO_REPLY),
                         LONG_TEXT, name='test_chunking')
    # the first chunk is good either way, only the second may be lost
    assert coverage.covered == set(first) | ({last} if answered else set())
    assert coverage.unknown == ({} if answered else {last: 'no reply'})


def test_only_new_codepoints_are_queried():
    """A repeat or overlapping call asks only about what is not yet known."""
    # a second round-trip for 'A' or 'B' could only time out and be unknown
    coverages, written = run(mintty(65, 66) + mintty(67), 'AB', 'BAB', 'ABC',
                             name='test_only_new_codepoints_are_queried')
    assert all(coverage.covers(text)
               for coverage, text in zip(coverages, ('AB', 'BAB', 'ABC')))
    assert '\x1b]7771;?;65;66\x07' in written
    assert '\x1b]7771;?;67\x07' in written


def test_uncovered_is_cached_too():
    """A negative answer is remembered, and not asked for twice."""
    coverages, written = run(mintty(65, 66, missing=(66,)), 'AB', 'BB',
                             name='test_uncovered_is_cached_too')
    assert all(coverage.uncovered == {66} for coverage in coverages)
    assert written.count('\x1b]7771;?') == 1


def test_result_is_scoped_to_the_text_asked_about():
    """A cached codepoint outside the text is not reported back."""
    coverages, _ = run(mintty(65, 66), 'AB', 'A',
                       name='test_result_is_scoped_to_the_text_asked_about')
    assert coverages[1].sources == {65: 'system'}


def test_force_discards_cache():
    """force=True re-probes the protocol and re-asks every codepoint."""
    def child(term):
        term.ungetch(mintty(65, 66, missing=(66,)) + mintty(65, 66))
        assert term.get_font_coverage('AB', timeout=0.01).uncovered == {66}
        assert term.get_font_coverage(
            'AB', timeout=0.01, force=True).covered == {65, 66}
        return b'OK'

    assert 'OK' in pty_test(child, test_name='test_force_discards_cache')


def test_force_discards_unknown():
    """force=True asks again about a codepoint the terminal refused."""
    def child(term):
        # the first exchange is buffered, the second is answered live below: the two
        # cannot share a buffer, because reading is greedy and the first call would
        # swallow the second call's replies
        term.ungetch(NO_REPLY + PROBE +
                     '\x1b_25a1;q;cp=41;status=1;reason=malformed\x1b\\' + CPR)
        assert term.get_font_coverage('A', timeout=0.01).unknown == {65: 'malformed'}
        coverage = term.get_font_coverage('A', timeout=1.0, force=True)
        assert coverage.unknown == {} and coverage.covered == {65}
        return b'OK'

    def parent(master_fd):
        # force=True re-probes from scratch: mintty, then 's', then 'q'.  Each marker
        # appears twice, once for the buffered first call and once for this one.
        data, stime = b'', time.time()
        for marker, reply in ((b'\x1b]7771;?', CPR),
                              (b'\x1b_25a1;s\x1b\\', PROBE),
                              (b'\x1b_25a1;q;cp=41\x1b\\', glyph((65, 'system')))):
            while data.count(marker) < 2:
                if (remaining := 2.0 - (time.time() - stime)) <= 0:
                    return
                if select.select([master_fd], [], [], remaining)[0]:
                    data += os.read(master_fd, 4096)
            os.write(master_fd, reply.encode())

    assert 'OK' in pty_test(child, parent, test_name='test_force_discards_unknown')


@pytest.mark.parametrize('coverage, covered, uncovered', [
    (SAMPLE, {0x41, 0x43}, {0x42}),
    (FontCoverage(), set(), set()),
], ids=['answered', 'empty'])
def test_covered_and_uncovered_partition_sources(coverage, covered, uncovered):
    """Every source entry is either covered or uncovered, never both."""
    assert (coverage.covered, coverage.uncovered) == (covered, uncovered)
    assert coverage.covered | coverage.uncovered == set(coverage.sources)


def test_empty_coverage_is_falsey():
    """An unsupported result is falsey and reports nothing."""
    coverage = FontCoverage()
    assert not coverage and coverage.supported is False
    assert coverage.protocol is None and coverage.unknown == {}
    assert coverage.covers('') is True and not coverage.covers('A')


@pytest.mark.parametrize('item, expected', [
    (0x41, True), ('A', True),        # covered, by codepoint or by character
    (0x42, False), ('B', False),      # uncovered
    (0x44, False), ('D', False),      # unanswered is not coverage
    (0x45, False), ('E', False),      # never queried
])
def test_coverage_contains(item, expected):
    """Membership works by codepoint and by single character alike."""
    assert (item in SAMPLE) is expected


@pytest.mark.parametrize('item', ['AB', '', None, 1.5, b'A', ('A',)],
                         ids=['too-long', 'empty', 'none', 'float', 'bytes', 'tuple'])
def test_coverage_contains_rejects_non_codepoints(item):
    """A value that cannot be a codepoint raises, rather than answering False."""
    with pytest.raises(TypeError, match='must be an integer or a string of length 1'):
        assert item in SAMPLE


@pytest.mark.parametrize('text, expected', [
    ('A', True), ('AAA', True), ('AC', True),
    ('AB', False),   # uncovered
    ('AD', False),   # unanswered
    ('AE', False),   # never queried
])
def test_coverage_covers_requires_every_codepoint(text, expected):
    """covers() is all-or-nothing across the text given."""
    assert SAMPLE.covers(text) is expected


@pytest.mark.parametrize('other, equal', [
    (FontCoverage(sources={0x41: 'system'}, protocol='mintty'), True),
    (FontCoverage(sources={0x41: ''}, protocol='mintty'), False),
    (FontCoverage(sources={0x41: 'system'}, protocol='glyph'), False),
    (FontCoverage(sources={0x41: 'system'}, unknown={0x42: 'no reply'},
                  protocol='mintty'), False),
    ('not a coverage', False),
])
def test_coverage_equality(other, equal):
    """Results compare by value, and do not compare with foreign types."""
    assert (FontCoverage(sources={0x41: 'system'}, protocol='mintty') == other) is equal


def test_coverage_repr():
    """The repr describes a result by count."""
    assert repr(SAMPLE) == (
        "FontCoverage(protocol='glyph', covered=2, uncovered=1, unknown=1)")


def test_coverage_equality_returns_notimplemented():
    """Comparison with a foreign type defers, rather than claiming inequality."""
    # returning NotImplemented rather than False is what lets the reflected
    # comparison run, so the dunder is called deliberately here
    # pylint: disable-next=unnecessary-dunder-call
    assert FontCoverage().__eq__('not a coverage') is NotImplemented


@pytest.mark.parametrize('text, expected', [
    ('\x1b]7771;!;65;66;67\x07', ';65;66;67'),
    ('\x1b]7771;!;65;;67\x07', ';65;;67'),      # the middle one uncovered
    ('\x1b]7771;!;;;\x07', ';;;'),              # three queried, none covered
    ('\x1b]7771;!\x07', ''),                    # nothing was asked about
    ('\x1b]7771;!;128512\x1b\\', ';128512'),    # ST terminates, and past the BMP
    ('\x1b]7771;?;65\x07', None),               # a query, not a reply
])
def test_mintty_response_pattern(text, expected):
    """_RE_MINTTY_FONT_RESPONSE parses the covered codepoint list."""
    match = _RE_MINTTY_FONT_RESPONSE.search(text)
    assert (match.group(1) if match else None) == expected


@pytest.mark.parametrize('text, expected', [
    ('\x1b_25a1;q;cp=41;status=system\x1b\\', ('41', 'system', None)),
    ('\x1b_25a1;q;cp=42;status=\x1b\\', ('42', '', None)),
    ('\x1b_25a1;q;cp=43;status=system,glossary\x1b\\', ('43', 'system,glossary', None)),
    # the reason of an error reply is captured, and kept out of the status
    ('\x1b_25a1;q;cp=e000;status=2;reason=out_of_namespace\x1b\\',
     ('e000', '2', 'out_of_namespace')),
])
def test_glyph_q_response_pattern(text, expected):
    """_RE_GLYPH_PROTOCOL_Q_RESPONSE parses cp, status and reason."""
    assert _RE_GLYPH_PROTOCOL_Q_RESPONSE.search(text).groups() == expected


@pytest.mark.parametrize('text, expected', [
    ('\x1b_25a1;s;fmt=glyf,colrv0\x1b\\', ';fmt=glyf,colrv0'),
    ('\x1b_25a1;s;fmt=\x1b\\', ';fmt='),
    ('\x1b_25a1;s\x1b\\', None),                       # a bare verb
    ('\x1b_25a1;q;cp=41;status=system\x1b\\', None),    # another verb's reply
])
def test_glyph_s_response_pattern(text, expected):
    """_RE_GLYPH_PROTOCOL_S_RESPONSE captures the advertised parameters."""
    match = _RE_GLYPH_PROTOCOL_S_RESPONSE.search(text)
    assert (match.group(1) if match else None) == expected


@pytest.mark.parametrize('kwargs', [
    {'force_styling': True, 'is_a_tty': False},
    {'force_styling': False},
], ids=['not-a-tty', 'no-styling'])
def test_query_boundary_multiple_no_terminal(kwargs):
    """_query_boundary_multiple returns None without writing anything."""
    term = TestTerminal(stream=io.StringIO(), **kwargs)
    term._is_a_tty = kwargs.get('is_a_tty', True)
    assert term._query_boundary_multiple(
        'x', _RE_GLYPH_PROTOCOL_Q_RESPONSE, 0.01) is None


def test_query_boundary_multiple_pushes_back_trailing_input():
    """Keystrokes arriving after the boundary are given back to inkey()."""
    def child(term):
        term.ungetch('\x1b_25a1;q;cp=41;status=system\x1b\\' + CPR + 'xyz')
        matches = term._query_boundary_multiple(
            '', _RE_GLYPH_PROTOCOL_Q_RESPONSE, 0.01)
        assert [match.group(1) for match in matches] == ['41']
        with term.cbreak():
            assert ''.join(term.inkey(timeout=0.01) for _ in range(3)) == 'xyz'
        return b'OK'

    assert 'OK' in pty_test(
        child, test_name='test_query_boundary_multiple_pushes_back_trailing_input')


def test_query_boundary_multiple_without_replies():
    """A bare boundary yields an empty list, distinct from None."""
    def child(term):
        term.ungetch(CPR)
        assert term._query_boundary_multiple(
            '', _RE_GLYPH_PROTOCOL_Q_RESPONSE, 0.01) == []
        return b'OK'

    assert 'OK' in pty_test(
        child, test_name='test_query_boundary_multiple_without_replies')
