/** Floor map geometry shared by the editor and its tests: a 1000 x 600 space, shelves above y 540. */
import type { Aisle } from "./api";

export const W = 1000, FLOOR = 540;
export const MAX_BLOCKS = 48;          // across all floors; the API enforces the same cap

/** A free spot for a new block on this floor: the requested size first, then smaller ones, scanning from the top left.
 *  Null when even a small block would overlap something. */
export function freeSpot(blocks: Pick<Aisle, "x" | "y" | "w" | "h">[], w: number, h: number): { x: number; y: number; w: number; h: number } | null {
  const GAP = 10;
  const clear = (x: number, y: number, bw: number, bh: number) =>
    blocks.every((b) => x + bw + GAP <= b.x || b.x + b.w + GAP <= x || y + bh + GAP <= b.y || b.y + b.h + GAP <= y);
  for (const [bw, bh] of [[w, h], [w, 200], [w, 120], [60, 60]]) {
    for (let y = 0; y + bh <= FLOOR; y += 20)
      for (let x = 0; x + bw <= W; x += 20) if (clear(x, y, bw, bh)) return { x, y, w: bw, h: bh };
  }
  return null;
}

