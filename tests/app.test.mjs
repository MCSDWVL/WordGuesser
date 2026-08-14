import test from "node:test";
import assert from "node:assert/strict";
import { buildRounds, resolveSeed, seededRandom, utcDateSeed } from "../app.js";

test("UTC dates use calendar-date seeds", () => {
  assert.equal(utcDateSeed(new Date("2026-08-14T23:59:00-07:00")), "2026-08-15");
  assert.equal(resolveSeed("?seed=fixture", new Date()), "fixture");
});

test("a seed produces the same five unique rounds", () => {
  const data = {
    words: Array.from({ length: 10 }, (_, i) => ({ word: `realword${i}`, definition: "A fixture definition." })),
    fakes: Array.from({ length: 10 }, (_, i) => `fakeword${i}`),
  };
  const first = buildRounds(data, "2026-08-14");
  const second = buildRounds(data, "2026-08-14");
  assert.deepEqual(first, second);
  assert.equal(first.length, 5);
  assert.equal(new Set(first.map(({ word }) => word)).size, 5);
  assert.ok([2, 3].includes(first.filter(({ kind }) => kind === "real").length));
});

test("seeded random is repeatable", () => {
  const one = seededRandom("same");
  const two = seededRandom("same");
  assert.deepEqual([one(), one(), one()], [two(), two(), two()]);
});
