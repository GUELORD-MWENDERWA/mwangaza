# Tâche 4.20.2 — École neuve : états vides et parcours de bout en bout (C4)

Issue #179 · branche `tache/4.20.2-ecole-neuve`. Suite de la 4.20.1 (la liste « Mise en route »).

## États vides
- Texte de chaque écran de la Gestion relevé dans un espace d'essai vide (20 écrans et leurs onglets). La plupart disent déjà quoi faire (année, niveaux, classes, frais, taux, caisse, appareils).
- Corrigés : accueil d'après connexion (rien ne menait à la liste « Mise en route » : elle y est affichée), liste des élèves d'une école sans élève, invitations au portail sans classe.

## Parcours Playwright `e2e/ecole-neuve.spec.ts`
- Console : le super-admin crée un espace **d'essai** (vide comme un espace réel, mais supprimable : supprimé à la fin, règle 3 respectée) → mot de passe provisoire du directeur.
- Directeur : nouveau mot de passe, double authentification, liste « Mise en route » : année, niveau et classe, frais et taux, compte du caissier, caisse ; le caissier se connecte sur son appareil ; un élève inscrit avec sa famille ; la liste est terminée.
- Caissier : ouvre la caisse, encaisse 50 $, reçu imprimé, clôture ; argent vérifié sur le serveur. Parent : active son portail avec le code famille et voit le reçu.
- Le Portail (5174) rejoint les serveurs de Playwright. Numéros tirés au hasard en `010…` (la plage `000` est réservée à la démonstration).

## Regard senior
- Un seul long parcours, pas un par étape : ce qu'on prouve, c'est l'enchaînement. Ni hors-ligne ni erreur glissée ici (déjà dans `caisse.spec.ts`).
- Pas de test Vitest de libellé : le parcours passe par les écrans corrigés.
- Écrans vides où il n'y a rien à faire (impayés, annulations, clôtures, crédits, demandes) : laissés tels quels.
