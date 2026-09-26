import { createContext, useContext } from "react";

import type { School } from "./queries";

// École de l'adresse, chargée une fois par `SchoolGate` avant tout écran.
export const SchoolContext = createContext<School | null>(null);

export function useCurrentSchool(): School {
  const school = useContext(SchoolContext);
  if (!school) throw new Error("useCurrentSchool() hors de SchoolGate");
  return school;
}
