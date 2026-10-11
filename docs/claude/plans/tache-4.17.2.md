# Tâche 4.17.2 — Démonstration depuis la console

Issue #174, branche `tache/4.17.2-demo-console`. Références : `02` A6, `03` § 4 bis, `05`.

**Serveur** (`apps/schools`)
- Modèle `Demonstration` [G] (une ligne par espace créé dans la console) : profil (`small` → données `volcans`, `large` → `itig`), bloc de numéros (unique, 40–99), mot de passe chiffré, état (`filling`, `ready`, `failed`), étapes faites / total, remise à zéro demandée, demandeur. Part avec la ligne de l'école (`deletion.py`).
- `demonstrations.py` : `create` (limite `DEMO_SPACES_MAX`, un seul travail à la fois, bloc libre le plus petit), `fill` (tâche de fond, verrou commun avec la suppression, avancement écrit à chaque étape, s'arrête si l'espace part), `reset` (= `delete_space` puis recréation **dans la transaction qui efface la ligne** : même identifiant, même bloc, nouveau mot de passe), `access_sheet`.
- API console : `POST schools/demo/`, `POST schools/{id}/reset/`, `GET schools/{id}/access-sheet/?output=html|pdf` ; fiche : champ `demonstration`. `POST schools/` n'accepte plus `demo` (un espace de démonstration vide n'a pas de sens).
- `portal/demo.py` : activations refaites avec les comptes désactivés par la suppression.
- Comptes partagés : mot de passe et double authentification non modifiables pour un compte d'une fiche d'accès (`accounts.services`).

**Console** : « Nouvel espace » type Démonstration → code, nom, petite / grande école ; fiche : avancement (relu toutes les 2 s), carte « Démonstration » (fiche d'accès, remettre à zéro) ; page « Fiche d'accès » = aperçu du document du serveur + PDF. Maquette : `console/ecoles` complétée.

**Regard senior — retiré ou simplifié**
- Fiche d'accès : un seul gabarit du serveur pour l'écran et le PDF (pas d'API JSON ni d'écran React à part).
- Pas de « relancer le remplissage » : un espace en échec ou bloqué se remet à zéro ou se supprime.
- Pas de file d'attente : création refusée (409) tant qu'un espace se crée ou se supprime.
- Espaces de `make demo` (`itig`, `volcans`) : ni fiche ni remise à zéro dans la console (`make demo` le fait).

**Tests** : super-admin seul ; limite et travail en cours refusés ; espace rempli dans son bloc, fiche d'accès sans donnée d'une autre école ; remise à zéro (même identifiant, autre école intacte, comptes réactivés, nouveau mot de passe) ; mot de passe d'un compte partagé refusé. Vitest : création et avancement.

**Risques** : durée du remplissage d'une grande école (mesurée) ; `test_demo.py` lent → un seul test avec `-k`.
