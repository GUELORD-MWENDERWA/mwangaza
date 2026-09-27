import { describe, expect, it } from "vitest";

import { uuidv7 } from "./ids";

describe("uuidv7", () => {
  it("version 7, variante RFC, date lisible et ordre de création", () => {
    const id = uuidv7(Date.UTC(2026, 8, 27));
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(parseInt(id.replace(/-/g, "").slice(0, 12), 16)).toBe(Date.UTC(2026, 8, 27));
    expect(uuidv7(1000) < uuidv7(2000)).toBe(true);
    expect(uuidv7()).not.toBe(uuidv7());
  });
});
