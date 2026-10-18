import { describe, expect, it } from "vitest";
import { rules, summary, validate } from "../validate";
import { snapshot } from "../toast";
import { guard } from "../validate";

describe("validate", () => {
  it("reports blank mandatory fields with their label, and skips blank optional ones", () => {
    const errors = validate({ name: { label: "Shop name", value: "  " }, city: { label: "City", value: "", optional: true }, langs: { label: "Languages", value: "", missing: "Pick at least one language." } });
    expect(errors).toEqual({ name: "Shop name is required.", langs: "Pick at least one language." });
  });
  it("runs rules on filled fields, optional or not", () => {
    expect(validate({ e: { label: "Email", value: "owner@shop", rule: rules.email } })).toEqual({ e: "Enter a valid email address." });
    expect(validate({ e: { label: "Email", value: "owner@shop.in", rule: rules.email } })).toEqual({});
    expect(validate({ u: { label: "Feed", value: "http://x.com/a", rule: rules.https, optional: true } })).toEqual({ u: "Enter a link that starts with https://" });
    expect(validate({ p: { label: "Password", value: "12345", rule: rules.minLen(6, "Password") } }).p).toMatch(/at least 6/);
  });
  it("checks numbers", () => {
    const price = rules.number("Price", { min: 0.01 });
    expect(price("abc")).toMatch(/must be a number/);
    expect(price("0")).toMatch(/at least 0.01/);
    expect(price("49.5")).toBe("");
    const stock = rules.number("Stock", { integer: true });
    expect(stock("2.5")).toMatch(/whole number/);
    expect(rules.number("Points", { integer: true, nonZero: true, min: -100000 })("0")).toMatch(/cannot be zero/);
    expect(rules.number("Discount", { max: 90 })("95")).toMatch(/at most 90/);
  });
  it("summarises one or several problems, and guard raises a toast", () => {
    const fields = { a: { label: "Name", value: "" }, b: { label: "Price", value: "" } };
    expect(summary(validate(fields), fields)).toBe("Please check: Name, Price.");
    let seen = {};
    expect(guard(fields, (e) => { seen = e; })).toBe(false);
    expect(Object.keys(seen)).toEqual(["a", "b"]);
    expect(snapshot().at(-1)?.text).toBe("Please check: Name, Price.");
    expect(guard({ a: { label: "Name", value: "Atta" } }, () => {})).toBe(true);
  });
});
