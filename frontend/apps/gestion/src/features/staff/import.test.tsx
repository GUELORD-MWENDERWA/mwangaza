import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { json, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";
import { letterLinks } from "./ImportStaffPage";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const line = {
  line: 2,
  name: "Kambale Muhindo Josué",
  phone_text: "0971234567",
  roles_text: "Enseignant",
  status: "ready",
  issues: [],
};
const preview = {
  recorded: false,
  ready_count: 1,
  skipped_count: 0,
  error_count: 1,
  lines: [
    line,
    {
      ...line,
      line: 3,
      name: "Kahindo Grâce",
      roles_text: "Bibliothécaire",
      status: "error",
      issues: [{ code: "unknown_role", role: "Bibliothécaire" }],
    },
  ],
  added: [],
};
const person = (n: number, letter: boolean) => ({
  id: id(n),
  name: `Personne ${n}`,
  phone: `+24397123456${n}`,
  roles: ["Enseignant"],
  existing_account: !letter,
  letter,
});

describe("import du personnel (R.1)", () => {
  it("vérifie le fichier, crée les comptes prêts, puis propose les lettres d'accès", async () => {
    const all: Routes = {
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/roles/": { count: 0, next: null, previous: null, results: [] },
      "POST /api/staff/import/": json(preview),
    };
    const requests = mockApi(all);
    const posted = () => requests.filter((request) => request.method === "POST");
    const { user } = renderApp("/staff/import");

    // `FormData` et fichier de Node : le `Request` de Node ne lit pas ceux de jsdom.
    const form = await new Response(new URLSearchParams("a=b")).formData();
    vi.stubGlobal("FormData", form.constructor);
    const blob = await new Response("xlsx").blob();
    const file = Object.assign(blob, { name: "personnel.xlsx" }) as unknown as File;
    await user.upload(await screen.findByLabelText(/Fichier Excel/), file);
    await user.click(screen.getByRole("button", { name: "Vérifier le fichier" }));

    expect(await screen.findByText("Rôle inconnu : « Bibliothécaire »")).toBeTruthy();
    expect(String(posted()[0]?.body)).not.toContain('name="expected"');
    all["POST /api/staff/import/"] = json(
      { ...preview, recorded: true, added: [person(1, true), person(2, false)] },
      201,
    );
    await user.click(screen.getByRole("button", { name: "Créer 1 compte" }));

    expect(await screen.findByText("2 personnes ajoutées à l'école.")).toBeTruthy();
    expect(String(posted()[1]?.body)).toMatch(/name="expected"\r\n\r\n1\r\n/);
    // Une lettre seulement pour le nouveau compte : l'autre garde son mot de passe.
    const letter = screen.getByRole("link", { name: "Lettre 1" });
    expect(letter.getAttribute("href")).toBe(`/api/staff/access-letters/?ids=${id(1)}`);
  });

  it("imprime les lettres par paquets de 50", () => {
    const links = letterLinks(Array.from({ length: 51 }, (_, n) => id(n)));
    expect(links.map(({ from, to }) => [from, to])).toEqual([
      [1, 50],
      [51, 51],
    ]);
    expect(links[1]?.url).toBe(`/api/staff/access-letters/?ids=${id(50)}`);
  });
});
