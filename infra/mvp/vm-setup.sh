#!/usr/bin/env bash
# ONEVO MVP — one-time bootstrap on an Ubuntu 22.04 GPU VM.
# Run as root or with sudo after SSH to the VM.
set -euo pipefail

ONEVO_USER="${ONEVO_USER:-onevo}"
ONEVO_DIR="${ONEVO_DIR:-/opt/onevo}"
ACR_LOGIN_SERVER="${ACR_LOGIN_SERVER:-}"

echo "==> ONEVO VM setup (user=$ONEVO_USER dir=$ONEVO_DIR)"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg git ufw nginx certbot python3-certbot-nginx

# Docker Engine + Compose plugin
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# NVIDIA driver + container toolkit (GPU VM only — skip if no GPU)
if lspci 2>/dev/null | grep -qi nvidia; then
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "==> Install NVIDIA driver (ubuntu-drivers)..."
    apt-get install -y ubuntu-drivers-common
    ubuntu-drivers install --gpgpu || ubuntu-drivers autoinstall || true
  fi
  if ! dpkg -l | grep -q nvidia-container-toolkit; then
    echo "==> NVIDIA Container Toolkit..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      > /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update
    apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
  fi
  echo "==> GPU check:"
  nvidia-smi || echo "WARN: nvidia-smi failed — verify driver after reboot"
else
  echo "==> No NVIDIA GPU detected — cloud-ai will run on CPU (slow for pilot)."
fi

# Deploy user + ensure SSH admin can run docker
if ! id "$ONEVO_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$ONEVO_USER"
fi
usermod -aG docker "$ONEVO_USER" 2>/dev/null || true
if id azureuser >/dev/null 2>&1; then
  usermod -aG docker azureuser
fi

mkdir -p "$ONEVO_DIR/connector/dist"
chown -R "$ONEVO_USER:$ONEVO_USER" "$ONEVO_DIR"

# Host nginx site (TLS via certbot after DNS is pointed)
if [[ -f "$(dirname "$0")/nginx-host.conf" ]]; then
  cp "$(dirname "$0")/nginx-host.conf" /etc/nginx/sites-available/onevo
  ln -sf /etc/nginx/sites-available/onevo /etc/nginx/sites-enabled/onevo
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
fi

# Optional: persistent ACR login for deploy user
if [[ -n "$ACR_LOGIN_SERVER" ]]; then
  echo "==> Configure ACR login: docker login $ACR_LOGIN_SERVER"
  echo "    Run manually once with a service principal or admin credentials."
fi

# Firewall (adjust SSH source in production)
ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true
ufw --force enable || true

echo ""
echo "==> VM bootstrap complete."
echo "    1. Clone repo to $ONEVO_DIR (or let GitHub Actions deploy.sh rsync)"
echo "    2. Place .env at $ONEVO_DIR/.env (from infra/mvp/.env.production.example)"
echo "    3. Point DNS to this VM, then: certbot --nginx -d app.yourdomain -d api.yourdomain"
echo "    4. Run infra/mvp/deploy.sh from CI or manually after ACR images exist"
