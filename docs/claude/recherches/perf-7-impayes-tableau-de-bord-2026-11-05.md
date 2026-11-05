# PERF.7 — « Impayés » et tableau de bord en SQL (2026-11-05)

**Changement** : PostgreSQL calcule le reste de chaque frais dû (`finance.services.settled_charges` :
paiements non annulés et crédits utilisés, plafonnés à ce qui est dû) et ne renvoie que les frais en
retard (Impayés) ou une ligne par classe (tableau de bord). Les élèves qui ont une réduction en cours
gardent le calcul frais par frais (`charges_by_enrollment`), seul à répartir les réductions : pas de
troisième copie de `discount_shares`. Les fiches des élèves ne sont lues que pour la page affichée ou
l'export (`with_contacts`).

**Mesure** (base locale de `make demo` : `itig-demo`, 800 élèves, 482 en retard ; même machine, même
données, ancien code par `git stash`). Un processus neuf par écran, puis un processus comme un
travailleur Gunicorn (2 fils, chacun ouvre 3 fois les trois écrans). Python ne rend pas la mémoire au
système : la croissance du RSS est ce que garde le conteneur.

| | Avant | Après |
|---|---|---|
| Impayés, 1re page : mémoire / temps / requêtes | +32 Mo · 1,14 s · 7 | +4 Mo · 0,36 s · 10 |
| Impayés, chiffres clés | +32 Mo · 1,12 s · 9 | +5 Mo · 0,30 s · 10 |
| Tableau de bord | +27 Mo · 1,21 s · 17 | +3 Mo · 0,44 s · 19 |
| Travailleur à 2 fils (médianes liste / résumé / tableau) | +63 Mo · 2,07 / 2,09 / 1,71 s | +11 Mo · 0,53 / 0,80 / 0,59 s |

**Mêmes chiffres** : listes, chiffres clés, lignes du PDF et de l'Excel, totaux par classe et tableau
de bord comparés sur les deux écoles de la démo et 8 filtres : identiques ; seul l'ordre d'élèves ex
æquo (même nom ou même montant) change, désormais par inscription, donc stable d'une page à l'autre.
Test d'argent : `test_the_database_gives_the_student_balance_without_more_queries_for_more_students`
(paiement partiel, annulé, crédit utilisé, réduction retirée ; même nombre de requêtes avec 2 élèves
de plus) ; il échoue si on compte un paiement annulé ou oublie un crédit (erreurs glissées exprès).

**Limite du conteneur Django gardée à 576 Mo** : elle est fixée surtout par Argon2 (≈ 100 Mo par mot
de passe vérifié, un à la fois par processus) et les deux processus ; le gain se voit dans la mémoire
gardée après ces écrans. À revoir avec la carte « Santé » après la mise en ligne (lot 7, OPS.5).

**Pas fait** : `make perf` sur `make prod-local` (deux constructions des images du serveur et la démo
rechargée, sur une machine de 8 Go à 1,8 Go libres) ; la mesure ci-dessus compare les mêmes calculs.
