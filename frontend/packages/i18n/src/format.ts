// Dates et heures (skill `design`, « Formats d'affichage ») : 19/10/2026, 10:42, dans le fuseau
// de l'école (`School.timezone`, défaut Africa/Lubumbashi), jamais celui de l'appareil.
const LOCALES = { fr: "fr-FR", en: "en-GB" } as const;

function locale(language: string) {
  return LOCALES[language as keyof typeof LOCALES] ?? LOCALES.fr;
}

function parts(
  value: string | Date,
  language: string,
  timeZone: string,
  options: Intl.DateTimeFormatOptions,
) {
  return new Intl.DateTimeFormat(locale(language), { timeZone, ...options }).format(
    new Date(value),
  );
}

/** `19/10/2026` */
export function formatDate(value: string | Date, language: string, timeZone: string) {
  return parts(value, language, timeZone, { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Jour sans heure (`2026-09-07` de l'API → `07/09/2026`) : pas de fuseau, c'est une date du
 *  calendrier de l'école. */
export function formatDay(value: string, language: string) {
  return parts(`${value}T00:00:00Z`, language, "UTC", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** `10:42` */
/** `octobre 2026` : un mois du calendrier (`2026-10`), sans fuseau. */
export function formatMonth(month: string, language: string) {
  return parts(`${month}-01T00:00:00Z`, language, "UTC", { month: "long", year: "numeric" });
}

export function formatTime(value: string | Date, language: string, timeZone: string) {
  return parts(value, language, timeZone, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}

/** `19/10/2026 10:42` */
export function formatDateTime(value: string | Date, language: string, timeZone: string) {
  return `${formatDate(value, language, timeZone)} ${formatTime(value, language, timeZone)}`;
}

/** Dernière visite (M2) : `aujourd'hui 07:12` le jour même (dans le fuseau de l'école), sinon la
 *  date. `today` reçoit l'heure et renvoie le texte traduit. */
export function formatVisit(
  value: string | Date,
  language: string,
  timeZone: string,
  today: (time: string) => string,
  now: Date = new Date(),
) {
  const day = formatDate(value, language, timeZone);
  return day === formatDate(now, language, timeZone)
    ? today(formatTime(value, language, timeZone))
    : day;
}

/** `+243971183062` → `+243 97 118 30 62` (numéro de la RDC) ; les autres tels quels. */
export function formatPhone(phone: string): string {
  const match = /^\+243(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(phone);
  return match ? `+243 ${match.slice(1).join(" ")}` : phone;
}
