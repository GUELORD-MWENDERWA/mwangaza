// Fiche de cotes commune (8.1.2a) : un cours donné ensemble à plusieurs classes se note sur une
// seule page, mais les notes restent celles de chaque classe (`Grade` → `Evaluation` → cours de
// la classe). Une colonne réunit l'évaluation du même nom de chaque classe ; une évaluation
// ajoutée, changée ou retirée l'est dans toutes les classes qu'on peut encore modifier. Chaque
// classe garde son maximum de la période : la note de la période y est ramenée.
import type { Sheet } from "./data";
import { parseTenths, type SaveBody, serverTenths, toScore } from "./sheet";

/** Une classe du cours commun : son cours, sa feuille de la période, et si on peut la modifier
 *  (validée, ou date limite passée : non). */
export type Part = { course: string; className: string; sheet: Sheet; locked: boolean };

/** Une colonne : `ids` et `maxima`, l'identifiant et le maximum de l'évaluation dans le cours de
 *  chaque classe qui l'a déjà. `key` : l'identifiant chez la première classe qui l'a. */
export type Column = {
  key: string;
  name: string;
  ids: Record<string, string>;
  maxima: Record<string, number>;
};

const same = (a: string, b: string) =>
  a.trim().toLocaleLowerCase("fr") === b.trim().toLocaleLowerCase("fr");

/** Colonnes de la fiche commune, dans l'ordre des évaluations de chaque classe. Deux évaluations
 *  du même nom dans une même classe restent deux colonnes. */
export function mergeColumns(parts: Part[]): Column[] {
  const columns: Column[] = [];
  for (const part of parts) {
    for (const evaluation of part.sheet.evaluations) {
      const column = columns.find(
        (item) => !(part.course in item.ids) && same(item.name, evaluation.name),
      );
      if (column) {
        column.ids[part.course] = evaluation.id;
        column.maxima[part.course] = evaluation.max_score;
      } else {
        columns.push({
          key: evaluation.id,
          name: evaluation.name,
          ids: { [part.course]: evaluation.id },
          maxima: { [part.course]: evaluation.max_score },
        });
      }
    }
  }
  return columns;
}

/** Saisie « total » (8.4.0) : une colonne, au maximum de la période de chaque classe. `key` : la
 *  première évaluation existante, sinon `fallback` (gardé par la page). */
export function totalsColumn(parts: Part[], name: string, fallback: string): Column {
  const ids: Record<string, string> = {};
  const maxima: Record<string, number> = {};
  for (const part of parts) {
    const evaluation = part.sheet.evaluations[0];
    if (evaluation) ids[part.course] = evaluation.id;
    maxima[part.course] = part.sheet.maximum;
  }
  return { key: Object.values(ids)[0] ?? fallback, name, ids, maxima };
}

/** Le maximum commun des classes, ou `null` s'il diffère d'une classe à l'autre. */
export function sharedMax(column: Column): number | null {
  const values = new Set(Object.values(column.maxima));
  return values.size === 1 ? [...values][0]! : null;
}

/** Maximum de la colonne dans ce cours : le sien, sinon le plus haut des autres classes. */
export const columnMax = (column: Column, course: string) =>
  column.maxima[course] ?? Math.max(1, ...Object.values(column.maxima));

/** Une colonne ajoutée ou changée sur la fiche : même nom et même maximum dans les classes
 *  modifiables (`courses`) ; les autres gardent le leur. */
export function withMax(column: Column, courses: string[], max: number, name: string): Column {
  return {
    ...column,
    name,
    maxima: { ...column.maxima, ...Object.fromEntries(courses.map((course) => [course, max])) },
  };
}

export const cellKey = (course: string, enrollment: string, column: string) =>
  `${course}|${enrollment}|${column}`;

/** Notes du serveur, en dixièmes, par `élève|évaluation` (une inscription est d'une seule
 *  classe) : une lecture par case reste rapide avec douze classes. */
export function scoreIndex(parts: Part[]): Map<string, number> {
  return new Map(
    parts.flatMap((part) =>
      part.sheet.students.flatMap((row) =>
        row.scores.map((cell) => [
          `${row.enrollment_id}|${cell.evaluation_id}`,
          serverTenths(cell.score),
        ]),
      ),
    ),
  );
}

/** Note du serveur de cet élève dans l'évaluation de la colonne, s'il en a une. */
export function original(
  index: Map<string, number>,
  part: Part,
  enrollment: string,
  column: Column,
): number | undefined {
  const id = column.ids[part.course];
  return id === undefined ? undefined : index.get(`${enrollment}|${id}`);
}

type Build = {
  parts: Part[];
  columns: Column[];
  /** Colonnes retirées de la fiche (leurs notes sont effacées). */
  removed: Column[];
  /** Cases tapées, par `cellKey`. */
  cells: Record<string, string>;
  reason: string;
  /** Identifiant d'une évaluation à créer dans un cours ; la page le garde d'un envoi à l'autre. */
  mint: (column: Column, course: string) => string;
};

/** Ce que chaque classe modifiable envoie (`PUT …/grades/`), seulement si elle change ;
 *  `invalid` : une case refusée (rien n'est envoyé). Une colonne absente d'une classe y est créée
 *  (mêmes évaluations partout). */
export function buildBodies({ parts, columns, removed, cells, reason, mint }: Build) {
  const bodies = new Map<string, SaveBody>();
  const index = scoreIndex(parts);
  for (const part of parts) {
    if (part.locked) continue;
    const course = part.course;
    const idOf = (column: Column) => column.ids[course] ?? mint(column, course);
    const evaluations = columns.map((column) => ({
      id: idOf(column),
      name: column.name.trim(),
      max_score: columnMax(column, course),
    }));
    const grades: SaveBody["grades"] = [];
    for (const row of part.sheet.students) {
      columns.forEach((column, place) => {
        const key = cellKey(course, row.enrollment_id, column.key);
        if (!(key in cells)) return;
        const tenths = parseTenths(cells[key]!, evaluations[place]!.max_score);
        if (tenths === undefined) throw new InvalidCell();
        if (tenths === (original(index, part, row.enrollment_id, column) ?? null)) return;
        grades.push({
          enrollment_id: row.enrollment_id,
          evaluation_id: evaluations[place]!.id,
          score: tenths === null ? null : toScore(tenths),
        });
      });
    }
    const removedIds = removed.flatMap((column) =>
      column.ids[course] ? [column.ids[course]] : [],
    );
    const before = part.sheet.evaluations.map((e) => `${e.id}|${e.name}|${e.max_score}`);
    const after = evaluations.map((e) => `${e.id}|${e.name}|${e.max_score}`);
    const changed =
      grades.length > 0 ||
      removedIds.length > 0 ||
      before.length !== after.length ||
      before.some((value, index) => value !== after[index]);
    if (changed) {
      bodies.set(course, { evaluations, removed_evaluations: removedIds, grades, reason });
    }
  }
  return bodies;
}

export class InvalidCell extends Error {}

/** Identifiants des évaluations à créer, gardés d'un envoi à l'autre (un envoi refusé puis repris
 *  ne crée pas deux évaluations). La première classe reçoit `key` : la colonne garde son nom de
 *  case une fois relue du serveur ; les autres, un identifiant neuf (`fresh`, UUID v7). */
export function minter(fresh: () => string) {
  const given = new Map<string, string>();
  return (column: Column, course: string) => {
    const key = `${column.key}|${course}`;
    let id = given.get(key);
    if (id === undefined) {
      const taken =
        Object.values(column.ids).includes(column.key) ||
        [...given].some(([at, value]) => at.startsWith(`${column.key}|`) && value === column.key);
      id = taken ? fresh() : column.key;
      given.set(key, id);
    }
    return id;
  };
}
