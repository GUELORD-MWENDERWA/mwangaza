"""État public du domaine de la plateforme (OPS.3, OPS.4).

Appelé par `make deploy-check`. Deux lignes, qui avertissent sans jamais échouer :
- « domaine » (annuaire RDAP) : date d'expiration et verrou de transfert. Un domaine expiré
  ou transféré sans ton accord coupe toutes les écoles ;
- « e-mail » (DNS) : MX, SPF, DKIM et DMARC. Sans eux, `contact@` et `support@` ne reçoivent
  plus rien, ou n'importe qui peut écrire aux écoles en se faisant passer pour la plateforme.
Bibliothèque standard seulement (Python 3 de la machine).
"""

import datetime
import json
import re
import sys
import urllib.parse
import urllib.request

ALERTE_JOURS = 30
# Sélecteur DKIM du fournisseur des boîtes (LWS) : à changer avec le fournisseur.
DKIM_SELECTEUR = "dkim"
TYPES_DNS = {"MX": 15, "TXT": 16}


def expiration(domaine: str) -> None:
    # rdap.org renvoie vers l'annuaire du registre de l'extension (.com : Verisign).
    try:
        with urllib.request.urlopen(f"https://rdap.org/domain/{domaine}", timeout=20) as r:
            donnees = json.load(r)
        fin = next(e["eventDate"] for e in donnees["events"] if e["eventAction"] == "expiration")
    except (OSError, ValueError, KeyError, StopIteration):
        print("domaine : non vérifié (annuaire RDAP injoignable)")
        return
    fin = datetime.datetime.fromisoformat(fin.replace("Z", "+00:00"))
    jours = (fin - datetime.datetime.now(datetime.UTC)).days
    verrou = "client transfer prohibited" in donnees.get("status", [])
    etat = "actif" if verrou else "ABSENT"
    print(f"domaine : expire le {fin:%d/%m/%Y} (dans {jours} jours), verrou de transfert {etat}")
    aide = "chez le registraire (A-FAIRE.md § 9 octies)"
    if jours < ALERTE_JOURS:
        print(f"  ATTENTION : renouveler le domaine {aide}")
    if not verrou:
        print(f"  ATTENTION : activer le verrou de transfert {aide}")


def dns(nom: str, type_dns: str) -> list[str]:
    """Réponses publiques, par DNS sur HTTPS (sans `dig`) ; nom inexistant : liste vide."""
    requete = urllib.parse.urlencode({"name": nom, "type": type_dns})
    with urllib.request.urlopen(f"https://dns.google/resolve?{requete}", timeout=20) as r:
        reponse = json.load(r)
    if reponse["Status"] not in (0, 3):  # 3 : le nom n'existe pas
        raise OSError(f"DNS : code {reponse['Status']}")
    voulu = TYPES_DNS[type_dns]
    return [a["data"].strip('"') for a in reponse.get("Answer", []) if a["type"] == voulu]


def messagerie(domaine: str) -> None:
    try:
        mx = sorted(dns(domaine, "MX"), key=lambda d: int(d.split()[0]))
        spf = [t for t in dns(domaine, "TXT") if t.startswith("v=spf1")]
        dkim = dns(f"{DKIM_SELECTEUR}._domainkey.{domaine}", "TXT")
        dmarc = [t for t in dns(f"_dmarc.{domaine}", "TXT") if t.startswith("v=DMARC1")]
    except (OSError, ValueError, KeyError, IndexError):
        print("e-mail : non vérifié (DNS injoignable)")
        return
    alertes = []
    serveurs = ", ".join(d.split()[1].rstrip(".") for d in mx)
    if not mx:
        alertes.append("aucun MX : contact@ et support@ ne reçoivent plus rien")
    fin_spf = spf[0].split()[-1] if spf else ""
    if not spf:
        alertes.append("aucun SPF : n'importe quel serveur peut écrire au nom du domaine")
    elif len(spf) > 1:
        alertes.append(f"{len(spf)} enregistrements SPF : il en faut un seul")
    elif fin_spf not in ("-all", "~all"):
        alertes.append("SPF sans « -all » : n'importe quel serveur peut écrire au nom du domaine")
    # Clé vide (« p=; ») : clé retirée, les messages ne sont plus signés.
    signe = any(re.search(r"(?:^|;)\s*p=[^;\s]", t) for t in dkim)
    if not signe:
        alertes.append(f"pas de clé DKIM au sélecteur « {DKIM_SELECTEUR} »")
    trouve = re.search(r"(?:^|;)\s*p=(\w+)", dmarc[0]) if dmarc else None
    politique = trouve.group(1) if trouve else "absent"
    rapports = "avec rapports" if dmarc and "rua=" in dmarc[0] else "sans rapports"
    if politique not in ("quarantine", "reject"):
        alertes.append(f"DMARC {politique} : l'usurpation du domaine n'est pas bloquée")
    print(
        f"e-mail : MX {serveurs or 'absent'} ; SPF {fin_spf or 'absent'} ; "
        f"DKIM {'présent' if signe else 'absent'} ; DMARC {politique}, {rapports}"
    )
    for alerte in alertes:
        print(f"  ATTENTION : {alerte} (infra/README.md, « E-mail du domaine »)")


if __name__ == "__main__":
    expiration(sys.argv[1])
    messagerie(sys.argv[1])
