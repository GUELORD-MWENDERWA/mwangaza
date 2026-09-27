import { manage } from "./django";

// Données de démonstration comme au départ, avant et après les parcours : comptes, mots de passe
// (un parcours change celui de la secrétaire), double authentification, écoles pas suspendues,
// essais ratés oubliés. Après : `make dev-local` reste utilisable avec les comptes de `make demo`.
export default function globalSetup() {
  manage("demo");
  return () => manage("demo");
}
