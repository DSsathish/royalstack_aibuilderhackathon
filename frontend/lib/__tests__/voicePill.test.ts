import { describe, expect, it } from "vitest";
import { INTERRUPT_GRACE_MS, pillText, tapAction } from "../voicePill";

describe("voice pill", () => {
  it("maps a tap to what the shopper meant in each state", () => {
    expect(tapAction("idle", 99999)).toBe("start");
    expect(tapAction("speaking", 0)).toBe("interrupt");
    expect(tapAction("listening", 5000)).toBe("end");
    expect(tapAction("thinking", 5000)).toBe("end");
    expect(tapAction("connecting", 0)).toBe("end");
    expect(tapAction("listening", INTERRUPT_GRACE_MS - 1)).toBe("ignore");   // the reply just ended: that tap meant "interrupt"
  });

  it("says what is happening and where the sound goes", () => {
    expect(pillText("idle", "unknown", null)).toEqual({ label: "Talk", sub: "" });
    expect(pillText("connecting", "unknown", null).label).toBe("Connecting");
    expect(pillText("listening", "duplex", null)).toEqual({ label: "Listening", sub: "Headphones · talk over any time" });
    expect(pillText("listening", "speaker", null)).toEqual({ label: "Listening", sub: "Loudspeaker" });
    expect(pillText("listening", "unknown", null).sub).toBe("");
    expect(pillText("thinking", "speaker", "Checking the shelves")).toEqual({ label: "Checking the shelves", sub: "Loudspeaker" });
    expect(pillText("thinking", "unknown", null).label).toBe("Checking");
    expect(pillText("speaking", "speaker", null).sub).toBe("Tap to interrupt");
    expect(pillText("speaking", "duplex", null).sub).toBe("Talk over or tap to interrupt");
    expect(pillText("reconnecting", "duplex", null)).toEqual({ label: "Reconnecting", sub: "Keep talking" });
  });
});
