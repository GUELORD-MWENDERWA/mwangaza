import { describe, expect, it } from "vitest";

import { DEFAULT_LAYOUT, layoutQuery } from "./printOptions";

describe("layoutQuery", () => {
  it("n'envoie ni le sens habituel ni un seul exemplaire", () => {
    expect(layoutQuery(DEFAULT_LAYOUT)).toEqual({ paper: "a4" });
  });

  it("envoie le papier, le sens et les exemplaires choisis", () => {
    expect(layoutQuery({ paper: "a5", orientation: "landscape", perSheet: 3 })).toEqual({
      paper: "a5",
      orientation: "landscape",
      per_sheet: "3",
    });
  });
});
