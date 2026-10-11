#!/usr/bin/env bash
# Préparer le serveur de démonstration en ligne (4.6.2), une seule fois : `make deploy-setup`.
# Ubuntu 24.04 (Oracle Cloud Always Free, VM ARM) ; lancé en root par SSH depuis la machine.
# Peut être relancé sans dommage.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
ACCOUNT="${SUDO_USER:-ubuntu}"

echo "1/4 Mises à jour, puis mises à jour de sécurité automatiques (redémarrage à 4 h si besoin)"
apt-get update -q
apt-get upgrade -yq
# cron et gnupg : tâche de chaque nuit (purge des sessions, sauvegardes chiffrées).
apt-get install -yq unattended-upgrades ca-certificates curl rsync cron gnupg
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat >/etc/apt/apt.conf.d/52mwangaza <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF

echo "2/4 Docker (dépôt officiel) ; le compte $ACCOUNT peut lancer docker compose"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "$ACCOUNT"
systemctl enable --now docker

echo "3/4 Pare-feu : ports 80 et 443 ouverts (les images d'Oracle n'ouvrent que SSH)"
# Aussi à ouvrir dans la liste de sécurité du réseau, sur le site d'Oracle (A-FAIRE.md § 9 ter).
# Règle ajoutée au fichier relu au démarrage, sans y enregistrer celles de Docker.
for port in 80 443; do
  rule="-A INPUT -p tcp -m state --state NEW -m tcp --dport $port -j ACCEPT"
  if [ -f /etc/iptables/rules.v4 ] && ! grep -qF -- "$rule" /etc/iptables/rules.v4; then
    sed -i "/--dport 22 -j ACCEPT/a $rule" /etc/iptables/rules.v4
  fi
  iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport "$port" -j ACCEPT 2>/dev/null ||
    iptables -I INPUT -p tcp -m state --state NEW -m tcp --dport "$port" -j ACCEPT
done

echo "4/4 SSH : clé seulement, jamais root"
cat >/etc/ssh/sshd_config.d/60-mwangaza.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
systemctl reload ssh

echo "Serveur prêt. Suite : make deploy"
