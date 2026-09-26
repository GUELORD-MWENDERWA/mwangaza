import { describe, expect, it } from "vitest";

import { formatDate, formatDateTime, formatTime, formatVisit } from "./format";

const GOMA = "Africa/Lubumbashi";

describe("dates et heures", () => {
  it("dans le fuseau de l'école, jamais celui de l'appareil", () => {
    // 22:30 UTC = 00:30 le lendemain à Goma (UTC+2).
    expect(formatDateTime("2026-10-18T22:30:00Z", "fr", GOMA)).toBe("19/10/2026 00:30");
    expect(formatTime("2026-10-19T08:42:00Z", "en", GOMA)).toBe("10:42");
    expect(formatDate("2026-10-19T08:42:00Z", "en", GOMA)).toBe("19/10/2026");
  });

  it("dernière visite : « aujourd'hui » le jour même à l'école, sinon la date", () => {
    const now = new Date("2026-10-19T12:00:00Z");
    const today = (time: string) => `aujourd'hui ${time}`;
    expect(formatVisit("2026-10-19T05:12:00Z", "fr", GOMA, today, now)).toBe("aujourd'hui 07:12");
    expect(formatVisit("2026-10-16T05:12:00Z", "fr", GOMA, today, now)).toBe("16/10/2026");
    // Encore le 18 en UTC, mais déjà le 19 à Goma.
    expect(formatVisit("2026-10-18T23:00:00Z", "fr", GOMA, today, now)).toBe("aujourd'hui 01:00");
  });
});
