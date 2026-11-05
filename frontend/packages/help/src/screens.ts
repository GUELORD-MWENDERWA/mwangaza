/** Table écran → article d'aide : chaque application associe le premier segment de l'adresse
 *  (`cash`, `students`…) à la clé d'un article ; `""` : l'accueil. Sans correspondance : la liste. */
export type ScreenTable = Record<string, string>;

export function articleForPath(table: ScreenTable, pathname: string): string | null {
  const first = pathname.replace(/^\/(app\/)?/, "").split("/")[0] ?? "";
  return table[first] ?? null;
}
