import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId as id, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const year = { id: id(1), name: "2026-2027", is_current: true, terms: [] };
const group = (n: number, name: string) => ({
  id: id(n),
  academic_year: year.id,
  level: id(31),
  track: id(41),
  section: "A",
  name,
  capacity: 45,
  student_count: 40,
  homeroom_teacher: null,
});
const published = {
  id: id(200),
  title: "Congé de la Toussaint",
  body: "Pas de cours lundi.",
  audience: "all_families",
  class_groups: [],
  attachment: null,
  published_at: "2026-10-15T08:00:00Z",
  published_by: { id: id(5), last_name: "Furaha", middle_name: "", first_name: "Masika" },
  archived_at: null,
  read_by: 402,
};

describe("Annonces", () => {
  it("certaines classes : au moins une exigée, publiée pour les familles annoncées", async () => {
    const requests = mockApi({
      "GET /api/me/": me("study_director"),
      "GET /api/school/": school,
      "GET /api/announcements/": { count: 1, next: null, previous: null, results: [published] },
      "GET /api/academic-years/": [year],
      "GET /api/class-groups/": [group(60, "4e Électricité A"), group(61, "4e Électronique A")],
      "GET /api/announcements/recipients/": (request: Request) => ({
        families: new URL(request.url).searchParams.get("audience") === "all_families" ? 532 : 156,
      }),
      "POST /api/announcements/": { ...published, id: id(201), title: "Réunion des parents" },
    });
    const { user } = renderApp("/announcements");

    expect(await screen.findByText("Congé de la Toussaint")).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Publier pour 532 familles" })).toBeTruthy();
    await user.type(screen.getByLabelText("Titre"), "Réunion des parents");
    await user.type(screen.getByLabelText("Message"), "Samedi à 9 h.");
    await user.click(screen.getByRole("radio", { name: "Certaines classes" }));
    await user.click(screen.getByRole("button", { name: "Publier" }));
    expect(await screen.findByText("Choisissez au moins une classe.")).toBeTruthy();

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Classes destinataires" }),
      "4e Électricité A",
    );
    const button = await screen.findByRole("button", { name: "Publier pour 156 familles" });
    // `FormData` de Node : le `Request` de Node ne lit pas celui de jsdom.
    const form = await new Response(new URLSearchParams("a=b")).formData();
    vi.stubGlobal("FormData", form.constructor);
    await user.click(button);

    expect(await screen.findByText(/Annonce publiée/)).toBeTruthy();
    const sent = requests.filter((r) => r.method === "POST" && r.path === "/api/announcements/");
    expect(sent).toHaveLength(1);
    const body = String(sent[0]!.body);
    expect(body).toMatch(/name="audience"\s+class_groups/);
    expect(body).toMatch(new RegExp(`name="class_groups"\\s+${id(60)}`));
    expect(body).not.toContain(id(61));
    await waitFor(() => expect(screen.getByLabelText("Titre")).toHaveProperty("value", ""));
  });
});
