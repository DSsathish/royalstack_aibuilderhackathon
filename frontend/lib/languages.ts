/** Languages offered in the selector, native names first. Mirrors backend app/domain/languages.py; "auto" lets the
 *  model follow whatever the shopper speaks. */
export const LANGUAGES: { code: string; label: string }[] = [
  { code: "auto", label: "Auto" },
  { code: "en", label: "English" }, { code: "ta", label: "தமிழ்" }, { code: "hi", label: "हिन्दी" }, { code: "te", label: "తెలుగు" },
  { code: "kn", label: "ಕನ್ನಡ" }, { code: "ml", label: "മലയാളം" }, { code: "mr", label: "मराठी" }, { code: "bn", label: "বাংলা" },
  { code: "gu", label: "ગુજરાતી" }, { code: "ar", label: "العربية" }, { code: "de", label: "Deutsch" }, { code: "es", label: "Español" },
  { code: "fr", label: "Français" }, { code: "id", label: "Bahasa Indonesia" }, { code: "it", label: "Italiano" }, { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" }, { code: "nl", label: "Nederlands" }, { code: "pl", label: "Polski" }, { code: "pt", label: "Português" },
  { code: "ru", label: "Русский" }, { code: "th", label: "ไทย" }, { code: "tr", label: "Türkçe" }, { code: "vi", label: "Tiếng Việt" }, { code: "zh", label: "中文" },
];

/** Script-based guess of a text's language, for read-aloud voices when the shopper has not chosen one. */
export function scriptLanguage(text: string): string {
  const scripts: [RegExp, string][] = [
    [/[஀-௿]/, "ta"], [/[ఀ-౿]/, "te"], [/[ಀ-೿]/, "kn"], [/[ഀ-ൿ]/, "ml"],
    [/[ঀ-৿]/, "bn"], [/[઀-૿]/, "gu"], [/[ऀ-ॿ]/, "hi"], [/[؀-ۿ]/, "ar"],
    [/[぀-ヿ]/, "ja"], [/[가-힯]/, "ko"], [/[一-鿿]/, "zh"], [/[฀-๿]/, "th"], [/[Ѐ-ӿ]/, "ru"],
  ];
  for (const [re, code] of scripts) if (re.test(text)) return code;
  return "en";
}
