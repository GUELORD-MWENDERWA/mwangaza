"""État public du domaine de la plateforme, lu dans l'annuaire RDAP (OPS.3).

Appelé par `make deploy-check` : date d'expiration et verrou de transfert. Un domaine
expiré ou transféré sans ton accord coupe toutes les écoles. Avertit, n'échoue jamais.
Bibliothèque standard seulement (Python 3 de la machine).
"""

import datetime
import json
import sys
import urllib.request

ALERTE_JOURS = 30


def main(domaine: str) -> None:
    # rdap.org renvoie vers l'annuaire du registre de l'extension (.com : Verisign).
    try:
        with urllib.request.urlopen(f"https://rdap.org/domain/{domaine}", timeout=20) as r:
            donnees = json.load(r)
        fin = next(e["eventDate"] for e in donnees["events"] if e["eventAction"] == "expiration")
    except (OSError, ValueError, KeyError, StopIteration):
        print("non vérifié (annuaire RDAP injoignable)")
        return
    fin = datetime.datetime.fromisoformat(fin.replace("Z", "+00:00"))
    jours = (fin - datetime.datetime.now(datetime.UTC)).days
    verrou = "client transfer prohibited" in donnees.get("status", [])
    etat = "actif" if verrou else "ABSENT"
    print(f"expire le {fin:%d/%m/%Y} (dans {jours} jours), verrou de transfert {etat}")
    aide = "chez le registraire (A-FAIRE.md § 9 octies)"
    if jours < ALERTE_JOURS:
        print(f"  ATTENTION : renouveler le domaine {aide}")
    if not verrou:
        print(f"  ATTENTION : activer le verrou de transfert {aide}")


if __name__ == "__main__":
    main(sys.argv[1])
