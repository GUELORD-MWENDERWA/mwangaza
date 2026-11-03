import { useState, useSyncExternalStore } from "react";

/** Date (en-tête `Date`) de la dernière réponse reçue ou relue du cache : « vu le … » quand le
 *  réseau manque (HL.3). Une réponse du cache garde la date de sa lecture d'origine. */
let lastSeen: Date | null = null;

export function rememberSeen(response: Response) {
  const value = response.headers.get("Date");
  const date = value ? new Date(value) : null;
  if (date && !Number.isNaN(date.getTime())) lastSeen = date;
}

/** `null` tant que le réseau est là ; sinon la date des dernières données (ou maintenant). */
export function useOfflineSince(): Date | null {
  const online = useSyncExternalStore(
    (notify) => {
      window.addEventListener("online", notify);
      window.addEventListener("offline", notify);
      return () => {
        window.removeEventListener("online", notify);
        window.removeEventListener("offline", notify);
      };
    },
    () => navigator.onLine,
  );
  const [fallback] = useState(() => new Date());
  return online ? null : (lastSeen ?? fallback);
}
