# 4.24 — Installation obligatoire de la Gestion (hors plan, demande de l'utilisateur 2026-10-13)

**But** : le personnel utilise l'application installée (PWA), pas un onglet de navigateur : hors-ligne fiable, icône, notifications.
**Regard senior** : un logiciel natif (Electron/Tauri) refusé (`03`, journal) ; le PWA est déjà installable. Un navigateur ne peut ni fermer Chrome ni lancer l'application installée : on guide (« ouvre l'icône »).
**Décision de l'utilisateur** : obligatoire sur la Gestion **avec issue de secours** ; Portail inchangé (invitation douce, `InstallPage`).

- Logique d'installation partagée : `packages/ui/src/install.ts` (invite du navigateur, installé ?, iPhone ?, « vient d'être installée »), Portail l'utilise aussi.
- `features/install/InstallGate` dans `SchoolGate`, après le chargement de l'école, **avant la connexion** : écran plein page tant que l'application n'est pas installée (build de production seulement ; développement et Playwright intacts).
- Cas : Chrome/Edge/Android → bouton « Installer » ; iPhone → 3 étapes ; autre navigateur → menu du navigateur ; juste installée → « Ouvre Mwangaza depuis son icône » ; déjà installée mais ouverte dans un onglet → même message.
- Issue de secours (sinon un caissier bloqué) : après 2 refus, ou sur iPhone, ou 3 s sans invite : « Continuer dans le navigateur » = pour la session du navigateur seulement ; l'écran revient à la prochaine ouverture.
- Guide de démarrage : le guide par rôle existant (caissier, comptable) se lance déjà à la première ouverture de l'application ; l'écran d'installation contient les étapes par appareil.
- Tests : décision d'afficher l'écran (installée, développement, issue de secours), 2 refus, session. Une capture à 390 px.
- Docs : `A-FAIRE.md` (guide de démarrage pour les écoles), `03` (décision), `05`, `06`, `docs/guide` si l'écran apparaît.
