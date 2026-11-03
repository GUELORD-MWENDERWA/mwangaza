# ruff: noqa: E501
"""Brouillons des textes légaux (CTR.1, T5), rédigés par Claude, à faire relire par un juriste au
fait du droit congolais avant la première école payante. La version publiée est celle de la base :
ces textes ne servent qu'à la première (démonstration) ; ensuite, la console publie les suivantes."""

TEXTS = {
    "terms": {
        "title_fr": "Conditions générales d'utilisation et de vente",
        "title_en": "Terms of use and sale",
        "body_fr": """## 1. Objet
Les présentes conditions règlent l'utilisation de la plateforme de gestion scolaire par une école (« l'École ») et sa vente par l'éditeur (« le Prestataire »). Elles complètent le contrat de l'École.

## 2. Le service
Le Prestataire met à disposition de l'École, en ligne, les modules prévus par son contrat. Chaque école a son propre espace : ses données ne sont ni visibles ni modifiables par une autre école.

## 3. Comptes et responsabilité de l'École
L'École choisit qui a un compte et quels droits il a. Elle est responsable de l'usage que font ses comptes du service et de l'exactitude des données qu'elle saisit.

## 4. Prix et paiement
Le prix est celui du contrat, par élève inscrit et par période. Les factures sont payables sous 30 jours par espèces, virement ou Mobile Money. Une facture ne se modifie pas : une erreur se corrige par un avoir.

## 5. Durée et fin
Le contrat dure la période qu'il indique et se renouvelle selon ses termes. Faute de paiement après relance, le service passe en lecture seule avant d'être suspendu. À la fin du contrat, l'École peut exporter toutes ses données.

## 6. Données
Les données des élèves et des familles restent à l'École. Le Prestataire les traite seulement pour fournir le service, selon la politique de confidentialité.

## 7. Droit applicable
Le droit de la République démocratique du Congo s'applique ; à défaut d'accord, les tribunaux du siège du Prestataire sont compétents.""",
        "body_en": """## 1. Purpose
These terms govern the use of the school management platform by a school (“the School”) and its sale by the publisher (“the Provider”). They complete the School's contract.

## 2. The service
The Provider gives the School online access to the modules in its contract. Each school has its own space: its data cannot be seen or changed by another school.

## 3. Accounts and the School's responsibility
The School chooses who has an account and which rights it has. It is responsible for how its accounts use the service and for the accuracy of the data it enters.

## 4. Price and payment
The price is the one in the contract, per enrolled student and per period. Invoices are payable within 30 days by cash, bank transfer or Mobile Money. An invoice is never edited: a mistake is corrected by a credit note.

## 5. Term and end
The contract lasts the period it states and renews according to its terms. If payment is missing after reminders, the service becomes read-only before being suspended. When the contract ends, the School can export all of its data.

## 6. Data
Student and family data stay with the School. The Provider processes it only to provide the service, as described in the privacy policy.

## 7. Applicable law
The law of the Democratic Republic of the Congo applies; failing agreement, the courts of the Provider's registered office have jurisdiction.""",
    },
    "privacy": {
        "title_fr": "Politique de confidentialité",
        "title_en": "Privacy policy",
        "body_fr": """## Qui est responsable
Chaque école décide de ses données (élèves, familles, personnel, notes, paiements) : elle en est responsable. La plateforme les traite pour son compte, uniquement pour faire fonctionner le service.

## Ce que nous gardons
Identité et coordonnées des élèves, des familles et du personnel, inscriptions, notes, présences, paiements scolaires, journal des actions. Les photos envoyées sont ré-encodées.

## Qui peut les voir
Seulement les personnes de l'école concernée, selon leurs droits. Une famille voit ses propres enfants dans le portail. L'équipe de la plateforme n'y accède que pour le support, et chaque accès est écrit au journal.

## Combien de temps
Pendant le contrat, puis selon les durées légales ; les paiements d'un espace réel ne sont jamais effacés. Après le départ d'un élève, ses données sont réduites au minimum légal.

## Vos droits
Vous pouvez demander l'accès à vos données, leur correction ou leur export à l'école, qui peut les obtenir de la plateforme.

## Sécurité
Connexions chiffrées, mots de passe protégés, double authentification pour les comptes sensibles, sauvegardes chiffrées.""",
        "body_en": """## Who is responsible
Each school decides about its data (students, families, staff, grades, payments): it is responsible for it. The platform processes it on the school's behalf, only to run the service.

## What we keep
Identity and contact details of students, families and staff, enrolments, grades, attendance, school payments, the log of actions. Uploaded photos are re-encoded.

## Who can see it
Only people of the school concerned, according to their rights. A family sees its own children in the portal. The platform team accesses it only for support, and each access is written to the log.

## How long
During the contract, then as the law requires; payments of a real space are never erased. After a student leaves, their data is reduced to the legal minimum.

## Your rights
You can ask the school for access to your data, its correction or its export; the school can obtain it from the platform.

## Security
Encrypted connections, protected passwords, two-step sign-in for sensitive accounts, encrypted backups.""",
    },
    "register": {
        "title_fr": "Registre des traitements",
        "title_en": "Register of processing",
        "body_fr": """## Traitements pour le compte des écoles
- **Gestion des élèves et des familles** : inscription, classes, dossiers. Données : identité, coordonnées, photo. Conservation : durée du contrat puis minimum légal.
- **Frais scolaires et caisse** : frais, paiements, reçus. Données : montants, dates, payeur. Conservation : jamais effacés dans un espace réel.
- **Notes et bulletins** : cotes, délibération, bulletins. Données : résultats scolaires. Conservation : archivés par année.
- **Présences et discipline** : appels, absences. Conservation : l'année scolaire puis archive.
- **Communication** : annonces, convocations, messages aux familles. Données : numéros de téléphone.
- **Journal des actions** : qui a fait quoi, quand. Conservation : durée du contrat.

## Traitements de la plateforme
- **Abonnement** : contrats, factures, paiements de l'école. Conservation : durée légale comptable.
- **Support** : demandes et échanges avec l'équipe.""",
        "body_en": """## Processing on behalf of schools
- **Students and families**: enrolment, classes, records. Data: identity, contact details, photo. Kept: contract term, then the legal minimum.
- **School fees and cash desk**: fees, payments, receipts. Data: amounts, dates, payer. Kept: never erased in a real space.
- **Grades and report cards**: marks, deliberation, report cards. Data: school results. Kept: archived by year.
- **Attendance and discipline**: roll calls, absences. Kept: the school year, then archived.
- **Communication**: announcements, summons, messages to families. Data: phone numbers.
- **Action log**: who did what, when. Kept: contract term.

## Processing by the platform
- **Subscription**: contracts, invoices, payments of the school. Kept: legal accounting period.
- **Support**: requests and exchanges with the team.""",
    },
}
