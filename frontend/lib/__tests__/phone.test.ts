import { describe, expect, it } from "vitest";
import { normaliseIndianMobile, validateIndianMobile } from "../phone";

describe("Indian mobile validation", () => {
  it("normalises pasted formats to ten digits", () => {
    expect(normaliseIndianMobile("+91 98765 43210")).toBe("9876543210");
    expect(normaliseIndianMobile("09876543210")).toBe("9876543210");
    expect(normaliseIndianMobile("919876543210")).toBe("9876543210");
    expect(normaliseIndianMobile("98765-43210")).toBe("9876543210");
  });
  it("accepts real-looking numbers and explains the rest", () => {
    expect(validateIndianMobile("9003774140")).toBe("");
    expect(validateIndianMobile("98765")).toMatch(/more digit/);
    expect(validateIndianMobile("1234567890")).toMatch(/start with 6/);
    expect(validateIndianMobile("9999999999")).toMatch(/real number/);
    expect(validateIndianMobile("98765432101")).toMatch(/more than 10/);
  });
});
