#!/usr/bin/env bash
# Préparer le vrai serveur (4.6.3), une seule fois : `make deploy-setup`.
# Ubuntu 24.04 (AWS Lightsail) ; lancé en root par SSH depuis la machine.
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

echo "3/4 Pare-feu : ports 80 et 443 ouverts"
# Aussi à ouvrir côté hébergeur : onglet « Mise en réseau » de Lightsail (HTTP 80 et HTTPS 443 ; SSH 22 y est déjà).
# Règle ajoutée au fichier relu au démarrage, sans y enregistrer celles de Docker.
for port in 80 443; do
  rule="-A INPUT -p tcp -m state --state NEW -m tcp --dport $port -j ACCEPT"
  if [ -f /etc/iptables/rules.v4 ] && ! grep -qF -- "$rule" /etc/iptables/rules.v4; then
    sed -i "/--dport 22 -j ACCEPT/a $rule" /etc/iptables/rules.v4
  fi
  iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport "$port" -j ACCEPT 2>/dev/null ||
    iptables -I INPUT -p tcp -m state --state NEW -m tcp --dport "$port" -j ACCEPT
done

echo "4/4 SSH : clé seulement, jamais root (l'accès de $ACCOUNT par clé reste ouvert)"
# Garde-fou : sans clé enregistrée pour ce compte, couper les mots de passe fermerait la porte.
if [ ! -s "/home/$ACCOUNT/.ssh/authorized_keys" ]; then
  echo "Aucune clé dans /home/$ACCOUNT/.ssh/authorized_keys : SSH laissé tel quel." >&2
  exit 1
fi
# Le premier réglage lu l'emporte : « 00- » passe avant 50-cloud-init.conf (images Ubuntu).
rm -f /etc/ssh/sshd_config.d/60-mwangaza.conf
cat >/etc/ssh/sshd_config.d/00-mwangaza.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sshd -t && systemctl reload ssh

echo "Serveur prêt. Suite : make deploy"
