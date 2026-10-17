import { describe, expect, it } from "vitest";
import { LANGUAGES, scriptLanguage } from "../languages";

describe("languages", () => {
  it("offers auto plus a wide list with native names", () => {
    expect(LANGUAGES[0].code).toBe("auto");
    expect(LANGUAGES.length).toBeGreaterThan(20);
    expect(LANGUAGES.find((l) => l.code === "ta")?.label).toBe("தமிழ்");
  });
  it("guesses the language of a text from its script", () => {
    expect(scriptLanguage("அரிசி இருக்கா?")).toBe("ta");
    expect(scriptLanguage("आटा है?")).toBe("hi");
    expect(scriptLanguage("బియ్యం ఉందా?")).toBe("te");
    expect(scriptLanguage("ಅಕ್ಕಿ ಇದೆಯಾ?")).toBe("kn");
    expect(scriptLanguage("அரிசி 5 kg")).toBe("ta");
    expect(scriptLanguage("Do you have atta?")).toBe("en");
  });
});
