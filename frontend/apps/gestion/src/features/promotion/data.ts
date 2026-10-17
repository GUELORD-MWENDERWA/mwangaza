// Passage de classe (8.4.5) : place de l'année suivante proposée d'après la décision proclamée,
// réponse du parent (Portail), inscription en lot par l'école. Droit `students.edit` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Promotion = Schemas["Promotion"];
export type ClassPassage = Schemas["ClassPassage"];
export type PassageRow = ClassPassage["students"][number];

/** Décisions qui donnent une place l'année suivante. */
const PLACEABLE = new Set(["pass", "repeat", "orient"]);

export function usePromotion() {
  return useQuery({
    queryKey: keys.promotion,
    queryFn: () => call(api.GET("/api/promotion/")),
  });
}

export function useClassPassage(classId: string) {
  return useQuery({
    queryKey: [...keys.promotion, classId],
    queryFn: () =>
      call(api.GET("/api/class-groups/{id}/promotion/", { params: { path: { id: classId } } })),
    enabled: Boolean(classId),
  });
}

/** Ce que l'école peut faire d'une ligne : proposer (ou changer) la place, inscrire ou retirer
 *  une place proposée. Un élève déjà inscrit l'année suivante n'a plus rien à faire. */
export function rowActions(row: PassageRow) {
  const offered = row.place?.status === "offered";
  const done = row.enrolled_class !== null;
  return {
    offer: !done && PLACEABLE.has(row.decision),
    enroll: !done && offered,
    withdraw: !done && offered,
  };
}

/** Classe choisie pour la ligne : choix en cours, sinon place déjà proposée, sinon proposition. */
export function destination(row: PassageRow, drafts: Record<string, string>): string {
  return (
    drafts[row.enrollment] ??
    (row.place?.status === "offered" ? row.place.class_group : null) ??
    row.proposed_class ??
    ""
  );
}
