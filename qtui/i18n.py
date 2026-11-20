# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Italian source strings, English from the reviewed catalog shared with the macOS app.

Keys may contain printf tokens (%@, %lld, %d, %.1f…): a runtime string such as
"3 cicli completati" is matched against "%lld cicli completati" and rebuilt in English.
"""
import json, re
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / 'native/Localization/English.json'
_TOKEN = re.compile(r'%(?:\d+\$)?(?:@|lld|ld|d|g|[+ 0#-]*\d*(?:\.\d+)?f)|%%')
_language = 'it'
_english = {}
_patterns = []


def _load():
    global _english, _patterns
    try:
        _english = json.loads(CATALOG.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        _english = {}
    patterns = []
    for key in sorted(_english, key=len, reverse=True):
        tokens = list(_TOKEN.finditer(key))
        if not any(t.group() != '%%' for t in tokens):
            continue
        source, last = r'\A', 0
        for t in tokens:
            source += re.escape(key[last:t.start()])
            source += '%' if t.group() == '%%' else '(.+?)'
            last = t.end()
        source += re.escape(key[last:]) + r'\Z'
        try:
            patterns.append((re.compile(source, re.S), _english[key]))
        except re.error:
            pass
    _patterns = patterns


def set_language(code):
    global _language
    _language = 'en' if code == 'en' else 'it'
    if _language == 'en' and not _english:
        _load()


def language():
    return _language


def T(text):
    """Translate an Italian interface string (identity in Italian)."""
    if _language != 'en' or not text:
        return text
    exact = _english.get(text)
    if exact is not None:
        return exact
    for regex, fmt in _patterns:
        match = regex.match(text)
        if not match:
            continue
        out, last, group = '', 0, 1
        for t in _TOKEN.finditer(fmt):
            out += fmt[last:t.start()]
            if t.group() == '%%':
                out += '%'
            elif group <= len(match.groups()):
                captured = match.group(group)
                out += _english.get(captured, captured)
                group += 1
            last = t.end()
        return out + fmt[last:]
    return text


def has(text):
    if not _english:
        _load()
    return text in _english


def add(entries):
    """Strings introduced by the Qt interface (not present in the macOS catalog)."""
    if not _english:
        _load()
    for key, value in entries.items():
        _english.setdefault(key, value)


def F(key, *args):
    """String(format: T(key), args…): translate a printf key, then fill its tokens in order."""
    text = T(key)
    pieces, last, index = [], 0, 0
    for t in _TOKEN.finditer(text):
        pieces.append(text[last:t.start()])
        token = t.group()
        if token == '%%':
            pieces.append('%')
        elif index < len(args):
            value = args[index]
            index += 1
            spec = re.sub(r'^%(?:\d+\$)?', '%', token)
            if spec == '%@':
                pieces.append(str(T(value) if isinstance(value, str) else value))
            elif spec in ('%lld', '%ld', '%d'):
                pieces.append('%d' % int(value))
            else:
                pieces.append(spec % float(value))
        last = t.end()
    pieces.append(text[last:])
    return ''.join(pieces)
