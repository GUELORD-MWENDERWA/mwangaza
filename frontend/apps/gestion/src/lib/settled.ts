import { useEffect, useState } from "react";

/** La valeur une fois la saisie arrêtée `delay` ms : une requête par recherche, pas par touche. */
export function useSettled<T>(value: T, delay = 300): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
