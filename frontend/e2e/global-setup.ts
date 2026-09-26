import { manage } from "./django";

// Données de démonstration comme au départ : comptes, mots de passe, double authentification,
// écoles pas suspendues, essais ratés oubliés.
export default function globalSetup() {
  manage("demo");
}
