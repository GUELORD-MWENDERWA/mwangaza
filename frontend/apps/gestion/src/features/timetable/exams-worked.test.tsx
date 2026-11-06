import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId as id, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const account = () => {
  const base = me("head");
  return {
    ...base,
    school: {
      ...base.school!,
      permissions: [
        ...base.school!.permissions,
        "timetable.manage",
        "timetable.publish",
        "timetable.record_exceptions",
      ],
    },
  } as typeof base;
};

const term = {
  id: id(10),
  kind: "period",
  name: "",
  starts_on: "2026-11-10",
  ends_on: "2026-11-30",
};
const year = {
  id: id(1),
  name: "2026-2027",
  is_current: true,
  terms: [
    { id: id(9), kind: "semester", name: "", starts_on: null, ends_on: null, children: [term] },
  ],
};
const sitting = (n: number, course: string) => ({
  id: id(n),
  course: id(n + 100),
  course_name: course,
  class_group: id(50),
  class_name: "4HT Électricité A",
  kind: "exam",
  date: "2026-11-14",
  start: "08:00:00",
  end: "10:00:00",
  room: null,
  room_name: "",
  invigilator: null,
});
const schedule = (extra: object) => ({
  term: term.id,
  status: "draft",
  published_at: null,
  published_by: null,
  sittings: [sitting(21, "Mathématiques"), sitting(22, "Physique")],
  errors: 0,
  warnings: 0,
  issues: [],
  ...extra,
});

describe("Horaire des épreuves (EDT.5b)", () => {
  const routes = (current: object): Parameters<typeof mockApi>[0] => ({
    "GET /api/me/": account(),
    "GET /api/school/": school,
    "GET /api/academic-years/": [year],
    "GET /api/timetable/courses/": [],
    [`GET /api/timetable/exams/${term.id}/`]: current,
    [`POST /api/timetable/exams/${term.id}/publish/`]: schedule({ status: "published" }),
  });

  it("un conflit en rouge bloque « Publier »", async () => {
    const conflict = {
      level: "error",
      code: "class_overlap",
      sittings: [id(21), id(22)],
      values: { date: "2026-11-14" },
    };
    mockApi(routes(schedule({ errors: 1, issues: [conflict] })));
    renderApp("/exam-schedule");

    expect(await screen.findByText(/deux épreuves en même temps/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Publier" }).hasAttribute("disabled")).toBe(true);
  });

  it("sans conflit, la publication part", async () => {
    const requests = mockApi(routes(schedule({})));
    const { user } = renderApp("/exam-schedule");

    await user.click(await screen.findByRole("button", { name: "Publier" }));
    await waitFor(() =>
      expect(requests.some((r) => r.method === "POST" && r.path.endsWith("/publish/"))).toBe(true),
    );
  });
});

describe("Heures prestées (EDT.6)", () => {
  it("une absence : les heures cochées de l'horaire partent avec le motif", async () => {
    const month = new Date().toISOString().slice(0, 7);
    const requests = mockApi({
      "GET /api/me/": account(),
      "GET /api/school/": school,
      "GET /api/timetable/courses/": [
        {
          id: id(70),
          name: "Mathématiques",
          category: "main",
          class_group: id(50),
          teacher: id(5),
          teacher_name: "Kambale Jean",
          sessions: [],
          room: null,
          room_kind: "",
          spans_break: false,
          max_per_day: 2,
        },
      ],
      "GET /api/timetable/worked/": {
        month: `${month}-01`,
        school_days: 12,
        holidays: [],
        totals: { planned: 120, missed: 0, added: 0 },
        teachers: [],
      },
      "GET /api/timetable/worked/exceptions/": {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
      "GET /api/timetable/worked/day/": {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            entry: id(80),
            first: 1,
            length: 2,
            start: "07:30",
            end: "09:10",
            course: "Mathématiques",
            class_groups: ["4HT Électricité A"],
            recorded: null,
          },
        ],
      },
      "POST /api/timetable/worked/exceptions/": {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
    });
    const { user } = renderApp("/worked-hours");

    await user.click(await screen.findByRole("button", { name: "Noter une exception" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Enseignant"), "Kambale Jean");
    await user.click(await within(dialog).findByRole("checkbox"));
    await user.type(within(dialog).getByLabelText("Motif"), "Malade");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(requests.some((r) => r.method === "POST")).toBe(true));
    const sent = requests.find((r) => r.method === "POST")!.body as Record<string, unknown>;
    expect(sent).toMatchObject({
      kind: "teacher_absent",
      teacher: id(5),
      entries: [id(80)],
      reason: "Malade",
    });
  });
});
