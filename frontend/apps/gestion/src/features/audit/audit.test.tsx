import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const actor = { id: id(1), last_name: "Kasereka", middle_name: "", first_name: "Paluku" };
const log = (n: number, action: string, extra = {}) => ({
  id: id(100 + n),
  // 22:30 UTC = 00:30 le lendemain à Goma : l'heure de l'école, pas celle de l'appareil.
  created_at: "2026-10-18T22:30:00Z",
  action,
  domain: action.split(".")[0],
  actor,
  by_support: false,
  entity_type: "accounts.role",
  entity_id: id(200 + n),
  entity_label: "",
  before: null,
  after: null,
  ip: "41.243.12.7",
  user_agent: "Mozilla/5.0 Edg/140.0",
  ...extra,
});
const logs = [
  log(1, "roles.updated", {
    entity_label: "Caissier",
    before: { permissions: ["students.view"] },
    after: { permissions: ["students.view", "finance.collect_payment"] },
  }),
  log(2, "support.started", {
    actor: null,
    by_support: true,
    entity_type: "schools.school",
    entity_label: "École Alpha (fictive)",
    after: { reason: "Demande du directeur", expires_at: "2026-10-19T09:14:00Z" },
  }),
  log(3, "staff.roles_changed", {
    entity_type: "accounts.membership",
    entity_label: "Jeanne Kavira",
    before: { roles: [{ id: id(9), name: "Caissier" }] },
    after: {
      roles: [
        { id: id(9), name: "Caissier" },
        { id: id(8), name: "Chef d'atelier" },
      ],
    },
  }),
  log(4, "organisation.terms_changed", {
    entity_type: "schools.academicyear",
    entity_label: "2026-2027",
    before: {
      terms: [
        { kind: "semester", name: "", parent: null, starts_on: null, ends_on: null },
        { kind: "period", name: "", parent: 0, starts_on: null, ends_on: null },
      ],
    },
    after: {
      terms: [
        { kind: "semester", name: "", parent: null, starts_on: null, ends_on: null },
        { kind: "period", name: "P1", parent: 0, starts_on: "2026-09-07", ends_on: "2026-11-07" },
      ],
    },
  }),
  log(5, "auth.login", { entity_type: "", entity_label: "", after: { second_factor: "totp" } }),
];
const page = (results: unknown[], extra = {}) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
  ...extra,
});

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/audit/": page(logs),
    "GET /api/audit/actors/": [actor],
    ...extra,
  };
}

const detail = async (title: string) =>
  within((await screen.findByRole("heading", { name: title })).closest("section")!);

describe("Journal d'audit (M6)", () => {
  it("qui, quoi, quand (heure de l'école), sur quoi ; le support n'est pas nommé", async () => {
    mockApi(routes());
    renderApp("/audit");

    const rows = (await screen.findAllByRole("row")).slice(1).map((row) => row.textContent);
    expect(rows[0]).toBe("19/10 · 00:30PKPaluku KaserekaRôle modifiéCaissier");
    expect(rows[1]).toBe("19/10 · 00:30SASupport MwangazaConnexion supportÉcole Alpha (fictive)");
    expect(screen.getByText("1 – 5 sur 5 entrées")).toBeTruthy();
  });

  it("détail : avant / après traduits", async () => {
    mockApi(routes());
    const { user } = renderApp("/audit");

    const rows = await screen.findAllByRole("row");
    await user.click(within(rows[1]!).getByRole("button"));
    let card = await detail("Rôle modifié");
    expect(card.getByText("Voir les élèves")).toBeTruthy();
    expect(card.getByText("Voir les élèves, Encaisser")).toBeTruthy();
    expect(card.getByText("41.243.12.7")).toBeTruthy();

    await user.click(within(rows[3]!).getByRole("button"));
    card = await detail("Rôles changés");
    expect(card.getByText("Caissier, Chef d'atelier")).toBeTruthy();

    await user.click(within(rows[4]!).getByRole("button"));
    card = await detail("Découpage modifié");
    expect(card.getByText("P1 : 07/09/2026 → 07/11/2026")).toBeTruthy();
    expect(card.getByText("1re période : | → —")).toBeTruthy();

    await user.click(within(rows[5]!).getByRole("button"));
    card = await detail("Connexion");
    expect(card.getByText("code vérifié")).toBeTruthy();

    await user.click(within(rows[2]!).getByRole("button"));
    card = await detail("Connexion support");
    expect(card.getByText("Demande du directeur")).toBeTruthy();
    expect(card.getByText("19/10/2026 11:14")).toBeTruthy();
  });

  it("filtres et pages envoyés au serveur", async () => {
    const requests = mockApi(
      routes({ "GET /api/audit/": page(logs, { count: 120, next: "/api/audit/?page=2" }) }),
    );
    const { user } = renderApp("/audit");

    await screen.findByRole("option", { name: "Paluku Kasereka" });
    await user.selectOptions(screen.getByLabelText("Personne"), actor.id);
    await user.selectOptions(screen.getByLabelText("Action"), "organisation.class_created");
    await user.selectOptions(screen.getByLabelText("Domaine"), "organisation");
    await user.type(screen.getByLabelText("Du"), "2026-10-16");
    await user.type(screen.getByLabelText("Au"), "2026-10-19");
    await user.type(screen.getByLabelText(/Nom de l'objet/), "3e");
    await user.click(await screen.findByRole("button", { name: "Suivant" }));

    await waitFor(() =>
      expect(requests.filter((r) => r.path === "/api/audit/").at(-1)?.query).toEqual({
        actor: actor.id,
        action: "organisation.class_created",
        domain: "organisation",
        since: "2026-10-16",
        until: "2026-10-19",
        search: "3e",
        page: "2",
      }),
    );
  });

  it("promoteur : oui ; caissier : page refusée", async () => {
    mockApi(routes({ "GET /api/me/": me("promoter") }));
    renderApp("/audit");
    expect(await screen.findByRole("heading", { name: "Journal d'audit" })).toBeTruthy();
  });

  it("caissier : page refusée, rien n'est lu", async () => {
    const requests = mockApi(routes({ "GET /api/me/": me("cashier") }));
    renderApp("/audit");

    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/audit/")).toBe(false);
  });

  it("export Excel : seulement avec une période d'une année au plus, avec les filtres de l'écran", async () => {
    mockApi(routes());
    renderApp("/audit");

    const disabled = await screen.findByRole("button", { name: "Exporter (Excel)" });
    expect(disabled).toHaveProperty("disabled", true);
    fireEvent.change(screen.getByLabelText("Du"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("Au"), { target: { value: "2026-09-30" } });
    const link = await screen.findByRole("link", { name: "Exporter (Excel)" });
    expect(link.getAttribute("href")).toBe("/api/audit/export/?since=2026-09-01&until=2026-09-30");
    fireEvent.change(screen.getByLabelText("Du"), { target: { value: "2025-09-01" } });
    expect(screen.getByRole("button", { name: "Exporter (Excel)" })).toHaveProperty(
      "disabled",
      true,
    );
  });
});
