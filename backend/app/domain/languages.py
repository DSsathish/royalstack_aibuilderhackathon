"""Languages the app offers. The model understands and speaks many more than three; this table is what the selector
shows, what requests may name, and what the live transcriber gets as a hint. Keys are the app's short codes; values are
the English name, the native name and the BCP-47 tag the Gemini Live API takes (each tag verified against the model)."""

LANGUAGES: dict[str, tuple[str, str, str]] = {
    "en": ("English", "English", "en-IN"),
    "ta": ("Tamil", "தமிழ்", "ta-IN"),
    "hi": ("Hindi", "हिन्दी", "hi-IN"),
    "te": ("Telugu", "తెలుగు", "te-IN"),
    "kn": ("Kannada", "ಕನ್ನಡ", "kn-IN"),
    "ml": ("Malayalam", "മലയാളം", "ml-IN"),
    "mr": ("Marathi", "मराठी", "mr-IN"),
    "bn": ("Bengali", "বাংলা", "bn-IN"),
    "gu": ("Gujarati", "ગુજરાતી", "gu-IN"),
    "ar": ("Arabic", "العربية", "ar-XA"),
    "de": ("German", "Deutsch", "de-DE"),
    "es": ("Spanish", "Español", "es-ES"),
    "fr": ("French", "Français", "fr-FR"),
    "id": ("Indonesian", "Bahasa Indonesia", "id-ID"),
    "it": ("Italian", "Italiano", "it-IT"),
    "ja": ("Japanese", "日本語", "ja-JP"),
    "ko": ("Korean", "한국어", "ko-KR"),
    "nl": ("Dutch", "Nederlands", "nl-NL"),
    "pl": ("Polish", "Polski", "pl-PL"),
    "pt": ("Portuguese", "Português", "pt-BR"),
    "ru": ("Russian", "Русский", "ru-RU"),
    "th": ("Thai", "ไทย", "th-TH"),
    "tr": ("Turkish", "Türkçe", "tr-TR"),
    "vi": ("Vietnamese", "Tiếng Việt", "vi-VN"),
    "zh": ("Chinese", "中文", "cmn-CN"),
}
CODE_PATTERN = r"^(auto|" + "|".join(LANGUAGES) + r")$"   # for request validation; "auto" lets the model decide


def name(code: str) -> str:
    """English name for prompts; unknown codes come back as given."""
    return LANGUAGES[code][0] if code in LANGUAGES else code


def bcp47(code: str) -> str | None:
    return LANGUAGES[code][2] if code in LANGUAGES else None
