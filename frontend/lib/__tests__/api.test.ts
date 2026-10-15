import { describe, expect, it } from "vitest";
import { entranceParams, money } from "../api";

describe("entranceParams", () => {
  it("reads store, token and aisle from a query string", () => {
    expect(entranceParams("?store=demo&t=abc.def&aisle=A3")).toEqual({ store: "demo", token: "abc.def", aisle: "A3" });
  });
  it("aisle is optional", () => {
    expect(entranceParams("?store=demo&t=abc")).toEqual({ store: "demo", token: "abc", aisle: undefined });
  });
  it("missing token or store is null", () => {
    expect(entranceParams("?store=demo&aisle=A1")).toBeNull();
    expect(entranceParams("?t=abc")).toBeNull();
  });
});

describe("money", () => {
  it("formats rupees", () => {
    expect(money(1234.5)).toBe("₹1,234.50");
    expect(money(20)).toBe("₹20.00");
  });
});
