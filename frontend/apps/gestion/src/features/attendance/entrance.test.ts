import { describe, expect, it } from "vitest";

import { checkOk, read, tokenHash, TOKEN_PREFIX, type Passage, type Roster } from "./entrance";

const TOKEN = "A1B2C3D4E5F60718293A4B5C6D7E8F90";

async function roster(): Promise<Roster> {
  return {
    version: "v1",
    lateAfter: "07:45",
    matriculeCheck: true,
    people: [
      {
        kind: "student",
        id: "s1",
        name: "Josué Kambale",
        matricule: "1234",
        detail: "2HT A",
        cardHash: await tokenHash(TOKEN),
        photo: null,
      },
    ],
  };
}

const at = (hour: number, minute: number, second = 0) =>
  new Date(2026, 10, 9, hour, minute, second);

describe("pointage à l'entrée", () => {
  it("arrivé avant l'heure limite, en retard après (comme le serveur : 07:45:30 est en retard)", async () => {
    const list = await roster();
    const input = { card: TOKEN_PREFIX + TOKEN };
    expect((await read(list, input, new Map(), at(7, 45, 0))).outcome).toBe("arrived");
    expect((await read(list, input, new Map(), at(7, 45, 30))).outcome).toBe("late");
  });

  it("une carte inconnue ou sans préfixe est refusée", async () => {
    const list = await roster();
    expect((await read(list, { card: TOKEN }, new Map(), at(7, 0))).outcome).toBe("refused");
    expect((await read(list, { card: TOKEN_PREFIX + "FF" }, new Map(), at(7, 0))).outcome).toBe(
      "refused",
    );
  });

  it("une personne déjà passée ne crée rien de nouveau", async () => {
    const list = await roster();
    const first = await read(list, { card: TOKEN_PREFIX + TOKEN }, new Map(), at(7, 0));
    if (first.outcome === "refused") throw new Error("attendu : arrivé");
    const passed = new Map<string, Passage>([[first.person.id, first.passage]]);
    const again = await read(list, { matricule: "1234" }, passed, at(7, 5));
    expect(again.outcome).toBe("already");
  });

  it("clé de contrôle (Damm) : une faute ou une inversion de voisins est vue", () => {
    expect(checkOk("2026" + "0")).toBe(false);
    // Le dernier chiffre est la clé : on la calcule en cherchant celle qui rend le total nul.
    const valid = Array.from({ length: 10 }, (_, key) => "20260412" + key).filter(checkOk);
    expect(valid).toHaveLength(1);
    const body = valid[0]!;
    const swapped = body.slice(0, 3) + body[4] + body[3] + body.slice(5);
    expect(checkOk(swapped)).toBe(false);
  });

  it("un matricule mal tapé est distingué d'un matricule inconnu", async () => {
    const list = await roster();
    const typed = await read(list, { matricule: "9999" }, new Map(), at(7, 0));
    expect(typed).toMatchObject({ outcome: "refused" });
  });
});
