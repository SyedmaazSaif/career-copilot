"""Turn scraped job descriptions (often raw HTML) into readable plain text.

Several boards return the description as an HTML fragment. Rendered as plain
text that shows tags and entities (`<p>`, `&amp;`, `&#39;`), so we normalize it
once at ingest: unwrap block tags to line breaks, bullet list items, drop the
rest, and decode HTML entities.
"""
from __future__ import annotations

import html
import re

# Only touch text that actually contains a tag or a named/numeric entity, so
# plain prose containing a stray "<" (e.g. "revenue < $1M") is left alone.
_LOOKS_HTML = re.compile(r"</?[a-zA-Z][^>]*>|&[a-zA-Z]+;|&#\d+;")

_BR = re.compile(r"<br\s*/?>", re.I)
_LI_OPEN = re.compile(r"<li[^>]*>", re.I)
_BLOCK_CLOSE = re.compile(
    r"</(p|div|ul|ol|h[1-6]|tr|table|section|article|header|footer|blockquote)>",
    re.I,
)
_TAG = re.compile(r"<[^>]+>")
_TRAIL_WS = re.compile(r"[ \t]+\n")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NL = re.compile(r"\n{3,}")


def clean_description(raw: str) -> str:
    """Best-effort HTML → readable text. Idempotent on already-clean text."""
    if not raw:
        return ""
    text = raw
    if _LOOKS_HTML.search(text):
        text = _BR.sub("\n", text)
        text = _LI_OPEN.sub("\n• ", text)  # bullet for list items
        text = _BLOCK_CLOSE.sub("\n", text)
        text = _TAG.sub("", text)               # strip any remaining tags
        text = html.unescape(text)              # &amp; -> &, &#39; -> ', etc.
    text = text.replace("\xa0", " ").replace("​", "")
    text = _TRAIL_WS.sub("\n", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()
