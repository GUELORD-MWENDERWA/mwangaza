# Tâche 8.3.3 — Bulletin fidèle au formulaire officiel

**But** : le PDF du bulletin reprend le formulaire EPST (3e HT, IGE/P.S/137) : en-tête (drapeau dessiné, N° ID, province, ville, commune, code, N° perm.), colonnes aux largeurs mesurées sur le scan, lignes MAXIMA, cases noires, place et effectif, Application et Conduite par période, repêchage ou bloc Examen d'État (dernière année), police serif embarquée.
**Hors périmètre** : choix d'impression (8.3.4), texte seul sur le formulaire pré-imprimé (8.3.5), calcul d'Application et de Conduite (8.5.1 : cases vides à remplir à la main), armoiries (non reproduites : le QR code prend leur place).
**Données ajoutées** : `School.province/city/commune` (réglages de l'école), `Student.national_id` (N° ID) et `permanent_number` (N° perm.) (fiche, import), `Level.has_state_exam` (écran Niveaux).
**Critères** : un bulletin standard (2 semestres × 2 périodes) a les largeurs du scan (écart ≤ 1 mm, contrôlé en superposant le PDF au scan) ; autre structure : colonnes égales ; dernière année : Examen d'État ; tout vient des paramètres de l'école.
**Tests** : isolation et droits (existants) ; contenu : cases noires, lignes MAXIMA, bloc Examen d'État selon `has_state_exam`, N° perm. et N° ID, import des deux numéros.
**Documents** : 05, 06, 04, 07 § 4, reference.md, A-FAIRE § 11 si besoin, maquettes/README.
**Risques** : hauteur (cours nombreux) → hauteur de ligne calculée ; poids de la police → Regular + Bold seulement.
