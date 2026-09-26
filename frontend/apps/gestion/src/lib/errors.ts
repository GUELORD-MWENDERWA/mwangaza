// Erreurs de l'API traduites par leur code (`{code, detail}` ; `fields` pour une saisie refusée).
import { ApiError } from "@mwangaza/api";
import { fr, type TFunction } from "@mwangaza/i18n";
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

type ErrorKey = keyof typeof fr.errors;
type FieldErrorKey = keyof typeof fr.fieldErrors;

function isErrorKey(code: string): code is ErrorKey {
  return code in fr.errors;
}

/** Message d'une erreur pour l'utilisateur ; jamais le texte anglais du serveur. */
export function errorMessage(error: unknown, t: TFunction): string {
  if (!(error instanceof ApiError)) return t("errors.unknown", { code: "js" });
  if (error.code === "too_many_attempts") {
    return t("errors.too_many_attempts", { count: Math.ceil((error.retryAfter ?? 900) / 60) });
  }
  if (isErrorKey(error.code)) return t(`errors.${error.code}`);
  return t("errors.unknown", { code: error.code });
}

/** Message d'une erreur de champ renvoyée par le serveur. */
export function fieldMessage(code: string, t: TFunction): string {
  return code in fr.fieldErrors
    ? t(`fieldErrors.${code as FieldErrorKey}`)
    : t("fieldErrors.invalid");
}

/** Place les erreurs de champ du serveur sous les champs du formulaire ; renvoie le message
 *  général à afficher en haut (ou rien si tout est sous un champ). */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  fields: Path<T>[],
  setError: UseFormSetError<T>,
  t: TFunction,
): string | null {
  if (!(error instanceof ApiError) || error.code !== "invalid") return errorMessage(error, t);
  let placed = false;
  for (const [name, errors] of Object.entries(error.fields)) {
    const field = fields.find((candidate) => candidate === name);
    const [first] = errors;
    if (field && first) {
      setError(field, { type: "server", message: fieldMessage(first.code, t) });
      placed = true;
    }
  }
  return placed ? null : errorMessage(error, t);
}
