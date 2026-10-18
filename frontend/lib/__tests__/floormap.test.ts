import { describe, expect, it } from "vitest";
import { freeSpot } from "../floormap";

const block = (aisle: string, x: number, y: number, w: number, h: number) => ({ aisle, x, y, w, h, floor: 1, kind: "aisle" as const });

describe("freeSpot", () => {
  it("puts a new block where nothing is", () => {
    expect(freeSpot([], 90, 320)).toEqual({ x: 0, y: 0, w: 90, h: 320 });
    const spot = freeSpot([block("A1", 0, 0, 90, 420)], 90, 320)!;
    expect(spot.x).toBeGreaterThanOrEqual(100);                       // clear of A1 with a gap
  });
  it("shrinks the block when the floor is crowded, as on the demo map", () => {
    const demo = [80, 230, 380, 530, 680, 830].map((x, i) => block(`A${i + 1}`, x, 80, 90, 420));
    const spot = freeSpot(demo, 90, 320)!;
    expect(spot).not.toBeNull();
    for (const b of demo) {
      const overlaps = spot.x < b.x + b.w && b.x < spot.x + spot.w && spot.y < b.y + b.h && b.y < spot.y + spot.h;
      expect(overlaps).toBe(false);
    }
  });
  it("returns null when there is truly no room", () => {
    expect(freeSpot([block("Big", 0, 0, 1000, 540)], 90, 320)).toBeNull();
  });
});
