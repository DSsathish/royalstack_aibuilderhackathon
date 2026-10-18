import { describe, expect, it } from "vitest";
import { dockAction, stripText } from "../voiceText";

describe("the orb's tap", () => {
  it("starts when idle, interrupts while speaking, otherwise shows or hides the strip", () => {
    expect(dockAction("closed", "idle")).toBe("start");
    expect(dockAction("speaking", "speaking")).toBe("interrupt");
    expect(dockAction("listening", "listening")).toBe("toggle");
    expect(dockAction("listening", "thinking")).toBe("toggle");
    expect(dockAction("connecting", "connecting")).toBe("toggle");
  });
});

describe("the strip wording", () => {
  it("names the state and the echo verdict", () => {
    expect(stripText("connecting", "connecting", "unknown")).toEqual({ label: "Connecting", sub: "" });
    expect(stripText("reconnecting", "connecting", "duplex").label).toBe("Reconnecting, keep talking");
    expect(stripText("listening", "listening", "speaker")).toEqual({ label: "Listening. Just talk", sub: "Loudspeaker: tap the orb to interrupt" });
    expect(stripText("listening", "listening", "duplex")).toEqual({ label: "Listening. Just talk, interrupt any time", sub: "Headphones: talk over any time" });
    expect(stripText("speaking", "speaking", "speaker").label).toBe("Speaking. Tap the orb to interrupt");
    expect(stripText("listening", "thinking", "unknown")).toEqual({ label: "Checking", sub: "Checking for speaker echo" });
    expect(stripText("closed", "listening", "unknown", true)).toEqual({ label: "Listening. Speak, then pause", sub: "Push-to-talk mode" });
  });
});
