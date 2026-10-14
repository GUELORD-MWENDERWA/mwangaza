// Calculs de la grille de cours d'une classe (8.1) : examen = 2 × maximum de la période (aucun
// pour un atelier ou un laboratoire) ; total de l'année (T.G.) d'après le découpage de l'année
// (secondaire : 4 périodes et 2 examens → 8 × le maximum, ou 4 × sans examen). Rien n'est stocké.

export type GridRow = {
  period_max: number;
  has_exam: boolean;
  weekly_hours: number | null;
  teacher_id: string | null;
};

type TermLike = { kind: string; children?: TermLike[] };

/** Périodes et examens de l'année, à tous les niveaux du découpage. */
export function termCounts(terms: readonly TermLike[]) {
  const counts = { periods: 0, exams: 0 };
  const walk = (list: readonly TermLike[]) =>
    list.forEach((term) => {
      if (term.kind === "period") counts.periods += 1;
      if (term.kind === "exam") counts.exams += 1;
      walk(term.children ?? []);
    });
  walk(terms);
  return counts;
}

export type Counts = ReturnType<typeof termCounts>;

export function examMax(row: Pick<GridRow, "period_max" | "has_exam">): number | null {
  return row.has_exam ? 2 * row.period_max : null;
}

export function yearMax(row: Pick<GridRow, "period_max" | "has_exam">, counts: Counts): number {
  return row.period_max * counts.periods + (examMax(row) ?? 0) * counts.exams;
}

/** Totaux de la carte « Contrôle » et regroupements du bulletin (une ligne MAXIMA par maximum
 *  et par « avec / sans examen », du plus petit au plus grand). Lignes sans maximum ignorées. */
export function gridSummary(rows: readonly GridRow[], counts: Counts) {
  const valid = rows.filter((row) => row.period_max > 0);
  const groups = new Map<string, { max: number; hasExam: boolean; count: number }>();
  valid.forEach((row) => {
    const key = `${row.period_max}-${row.has_exam}`;
    const group = groups.get(key) ?? { max: row.period_max, hasExam: row.has_exam, count: 0 };
    group.count += 1;
    groups.set(key, group);
  });
  return {
    count: rows.length,
    period: valid.reduce((sum, row) => sum + row.period_max, 0),
    exam: valid.reduce((sum, row) => sum + (examMax(row) ?? 0), 0),
    year: valid.reduce((sum, row) => sum + yearMax(row, counts), 0),
    hours: rows.reduce((sum, row) => sum + (row.weekly_hours ?? 0), 0),
    assigned: rows.filter((row) => row.teacher_id).length,
    groups: [...groups.values()].sort(
      (a, b) => a.max - b.max || Number(b.hasExam) - Number(a.hasExam),
    ),
  };
}
