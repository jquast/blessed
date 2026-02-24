"""Tests for XTGETTCAP (DCS +q) terminal capability queries."""
# std imports
import io

# 3rd party
import pytest

# local
from blessed.keyboard import TermcapResponse, XTGETTCAP_CAPABILITIES
from .accessories import TestTerminal, as_subprocess


class TestTermcapResponseParsing:
    """TermcapResponse hex encoding/decoding and construction."""

    def test_hex_encode(self):
        assert TermcapResponse._hex_encode('TN') == '544e'
        assert TermcapResponse._hex_encode('colors') == '636f6c6f7273'

    def test_hex_decode(self):
        assert TermcapResponse._hex_decode('544e') == 'TN'
        assert TermcapResponse._hex_decode('636f6c6f7273') == 'colors'

    def test_hex_decode_invalid(self):
        assert TermcapResponse._hex_decode('zzzz') == 'zzzz'

    def test_supported_with_capabilities(self):
        caps = {'TN': 'xterm-256color', 'colors': '256'}
        resp = TermcapResponse(supported=True, capabilities=caps)
        assert resp.supported is True
        assert resp.terminal_name == 'xterm-256color'
        assert resp.num_colors == 256
        assert len(resp) == 2
        assert 'TN' in resp
        assert resp['TN'] == 'xterm-256color'
        assert resp.get('missing') is None
        assert resp.get('missing', 'default') == 'default'

    def test_unsupported(self):
        resp = TermcapResponse(supported=False)
        assert resp.supported is False
        assert resp.terminal_name is None
        assert resp.num_colors is None
        assert resp.rgb_bits is None
        assert len(resp) == 0

    def test_num_colors_non_integer(self):
        resp = TermcapResponse(supported=True, capabilities={'colors': 'abc'})
        assert resp.num_colors is None

    def test_rgb_bits(self):
        resp = TermcapResponse(supported=True, capabilities={'RGB': '8'})
        assert resp.rgb_bits == '8'

    def test_repr(self):
        resp = TermcapResponse(supported=True, capabilities={'TN': 'xterm'})
        assert 'supported=True' in repr(resp)
        assert 'TN' in repr(resp)

    def test_getitem_keyerror(self):
        resp = TermcapResponse(supported=True, capabilities={})
        with pytest.raises(KeyError):
            resp['nonexistent']

    def test_defaults_empty_capabilities(self):
        resp = TermcapResponse(supported=True)
        assert resp.capabilities == {}
        assert len(resp) == 0


class TestXtgettcapCapabilitiesList:
    """XTGETTCAP_CAPABILITIES constant."""

    def test_is_tuple_of_pairs(self):
        assert isinstance(XTGETTCAP_CAPABILITIES, tuple)
        for entry in XTGETTCAP_CAPABILITIES:
            assert len(entry) == 2
            assert isinstance(entry[0], str)
            assert isinstance(entry[1], str)

    def test_first_is_tn(self):
        assert XTGETTCAP_CAPABILITIES[0][0] == 'TN'

    def test_has_expected_count(self):
        assert len(XTGETTCAP_CAPABILITIES) == 23


class TestGetXtgettcap:
    """Terminal.get_xtgettcap() method."""

    def test_not_a_tty_returns_none(self):
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.get_xtgettcap(timeout=0.01) is None
        child()

    def test_does_xtgettcap_not_a_tty(self):
        @as_subprocess
        def child():
            term = TestTerminal(stream=io.StringIO(), force_styling=True,
                                is_a_tty=False)
            assert term.does_xtgettcap(timeout=0.01) is False
        child()

    def test_cached_result(self):
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True

            cached = TermcapResponse(supported=True,
                                     capabilities={'TN': 'test'})
            term._xtgettcap_cache = cached

            result = term.get_xtgettcap()
            assert result is cached
        child()

    def test_sticky_failure(self):
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_first_query_failed = True

            result = term.get_xtgettcap()
            assert result is None
        child()

    def test_force_bypasses_cache(self):
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True

            cached = TermcapResponse(supported=True,
                                     capabilities={'TN': 'old'})
            term._xtgettcap_cache = cached
            term._xtgettcap_first_query_failed = True

            # With force, it should attempt query (and timeout)
            result = term.get_xtgettcap(timeout=0.01, force=True)
            # Timeout means no response, so returns None
            assert result is None
        child()

    def test_parse_xtgettcap_responses(self):
        from blessed.terminal import Terminal
        raw = (
            '\x1bP1+r544e=787465726d\x1b\\'
            '\x1bP1+r636f6c6f7273=323536\x1b\\'
            '\x1bP0+r626365\x1b\\'
        )
        capabilities: dict = {}
        Terminal._parse_xtgettcap_responses(raw, capabilities)
        assert capabilities['TN'] == 'xterm'
        assert capabilities['colors'] == '256'
        assert 'bce' not in capabilities

    def test_parse_xtgettcap_boolean_capability(self):
        from blessed.terminal import Terminal
        raw = '\x1bP1+r626365\x1b\\'
        capabilities: dict = {}
        Terminal._parse_xtgettcap_responses(raw, capabilities)
        assert capabilities['bce'] == ''

    def test_does_xtgettcap_with_cached(self):
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_cache = TermcapResponse(
                supported=True, capabilities={'TN': 'test'})

            assert term.does_xtgettcap() is True
        child()

    def test_does_xtgettcap_unsupported(self):
        @as_subprocess
        def child():
            stream = io.StringIO()
            term = TestTerminal(stream=stream, force_styling=True)
            term._is_a_tty = True
            term._xtgettcap_first_query_failed = True

            assert term.does_xtgettcap() is False
        child()
