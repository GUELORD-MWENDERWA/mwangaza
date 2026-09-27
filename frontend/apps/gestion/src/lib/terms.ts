// Découpage de l'année (C1) : nom affiché de chaque semestre, trimestre, période ou examen. Un
// élément sans nom propre (`name` vide, créé par un modèle) prend un nom traduit d'après son genre
// et sa place : « Semestre 2 », « 3e période », « Examens du 1er semestre ».
import type { Schemas } from "@mwangaza/api";
import type { TFunction } from "@mwangaza/i18n";

export type TermKind = Schemas["TermLeaf"]["kind"];
export type TermShape = { kind: TermKind; name: string; children?: TermShape[] };

function groupLabel(kind: TermKind, n: number, t: TFunction) {
  return kind === "semester"
    ? t("organisation.terms.semester", { n })
    : t("organisation.terms.trimester", { n });
}

function examLabel(parent: TermShape | undefined, n: number, t: TFunction) {
  if (!parent) return t("organisation.terms.exams");
  if (parent.kind === "semester") {
    return n === 1
      ? t("organisation.terms.examsSemesterFirst")
      : t("organisation.terms.examsSemesterNth", { n });
  }
  return n === 1
    ? t("organisation.terms.examsTrimesterFirst")
    : t("organisation.terms.examsTrimesterNth", { n });
}

/** Nom de chaque élément de l'arbre (parents et enfants), l'école peut l'avoir renommé. */
export function termLabels(nodes: TermShape[], t: TFunction): Map<TermShape, string> {
  const labels = new Map<TermShape, string>();
  const groups = { semester: 0, trimester: 0 };
  let periods = 0;
  const label = (node: TermShape, parent?: TermShape, parentNumber = 0) => {
    if (node.kind === "semester" || node.kind === "trimester") {
      groups[node.kind] += 1;
      labels.set(node, node.name || groupLabel(node.kind, groups[node.kind], t));
      for (const child of node.children ?? []) label(child, node, groups[node.kind]);
      return;
    }
    if (node.kind === "period") {
      periods += 1;
      const text =
        periods === 1
          ? t("organisation.terms.periodFirst")
          : t("organisation.terms.periodNth", { n: periods });
      labels.set(node, node.name || text);
      return;
    }
    labels.set(node, node.name || examLabel(parent, parentNumber, t));
  };
  for (const node of nodes) label(node);
  return labels;
}

/** Découpage noté au journal (liste à plat, `parent` = place du parent) → arbre. */
export function snapshotTree(
  terms: { kind: TermKind; name: string; parent: number | null }[],
): (TermShape & { index: number })[] {
  const nodes = terms.map((term, index) => ({ ...term, index, children: [] as TermShape[] }));
  const roots: (TermShape & { index: number })[] = [];
  for (const node of nodes) {
    const parent = node.parent === null ? undefined : nodes[node.parent];
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}
