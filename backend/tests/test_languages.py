import re

from app.domain import languages


def test_language_table_and_pattern():
    assert len(languages.LANGUAGES) >= 20
    assert languages.name("ta") == "Tamil" and languages.bcp47("ta") == "ta-IN"
    assert languages.name("xx") == "xx" and languages.bcp47("xx") is None
    assert re.match(languages.CODE_PATTERN, "auto") and re.match(languages.CODE_PATTERN, "kn")
    assert not re.match(languages.CODE_PATTERN, "en-IN") and not re.match(languages.CODE_PATTERN, "")
