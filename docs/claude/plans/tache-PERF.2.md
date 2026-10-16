# Plan PERF.2 — PDF gardés (issue #276, branche tache/PERF.2-pdf-gardes)

**But** : un bulletin est mis en PDF une seule fois ; ensuite servi comme un fichier. Coût annoncé : une mise en page de bulletin ≈ 1,9 s de processeur + 13 Mo (inchangé, mais une seule fois) ; une réimpression = rendu du gabarit (≈ 30 ms) + lecture du fichier (+ réunion pypdf pour une classe) ; stockage ≈ taille du PDF par élève et par mode.
**Hors périmètre** : écran « bulletins » du Portail (n'existe pas : le service est prêt, l'écran vient avec 8.5.1b+) ; autres documents (reçus, fiches) ; allègement de la mise en page (PERF.3).
**Critères** : clé = empreinte du HTML du bulletin (notes, élève, gabarit, réglages de l'école, décalages) sans QR ni date ; réimpression = aucun WeasyPrint ; note ou gabarit modifié → nouvelle clé, ancien fichier effacé (un par élève et par mode) ; classe en tâche de fond : seules les pages manquantes sont refaites ; entrées non lues depuis 60 jours purgées.
**Tests** : isolation (clé identique dans deux écoles, jamais servie à l'autre) ; réimpression sans WeasyPrint ; changement d'une note → refait + ancien effacé ; classe partielle par la tâche de fond ; purge.
**Documents** : 05 (case + file), 06, 03 (journal des décisions + § 9), reference.md.
**Risques** : date et QR du PDF gardé = ceux du premier tirage (le QR reste valable : mêmes notes) ; audit toujours écrit à chaque impression.
