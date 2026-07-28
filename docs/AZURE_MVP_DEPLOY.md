# Azure MVP deployment runbook

Deploy ONEVO to a **single GPU Azure VM** with **Docker Compose**, built and released by **GitHub Actions**.

## Architecture

| Component | Where it runs |
|-----------|----------------|
| Backend, dashboard, cloud-ai, Postgres, Redis, MinIO | Azure GPU VM (Docker Compose) |
| Windows connector | **Shop PCs** — downloaded from dashboard after login |
| CI/CD | GitHub Actions → ACR → SSH deploy to VM |

Shop staff download `ONEVO-Connector-Setup-*.exe` from **Get started / Admin / Setup** in the dashboard. The backend serves the file from `/opt/onevo/connector/dist/` on the VM (mounted into the backend container). The connector service itself does **not** run in Azure.

## 1. Provision Azure (one time)

**Already provisioned** for this subscription — see [`infra/mvp/PROVISIONED.md`](../infra/mvp/PROVISIONED.md) for live resource names, VM IP, and GitHub secret mapping.

To provision from scratch (another subscription/region):

```bash
az login
export AZURE_RESOURCE_GROUP=onevo-mvp-rg
export AZURE_LOCATION=eastus
export AZURE_ACR_NAME=onevoacrmvp          # must be globally unique
export AZURE_VM_NAME=onevo-mvp-vm
./infra/mvp/provision-azure.sh
```

If GPU quota is unavailable, use CPU VM (`Standard_D2s_v5`) and `CLOUD_AI_DEVICE=cpu` in `.env` until quota is approved.

SSH to the VM and bootstrap:

```bash
ssh azureuser@<VM_PUBLIC_IP>
git clone <your-repo-url> /opt/onevo
cd /opt/onevo
sudo ACR_LOGIN_SERVER=<acr>.azurecr.io bash infra/mvp/vm-setup.sh
```

Edit `/etc/nginx/sites-available/onevo` — replace `YOUR_APP_DOMAIN` / `YOUR_API_DOMAIN`, reload nginx, then:

```bash
sudo certbot --nginx -d app.yourdomain.example -d api.yourdomain.example
```

Copy and fill secrets:

```bash
cp infra/mvp/.env.production.example /opt/onevo/.env
nano /opt/onevo/.env
```

## 2. GitHub secrets

Create a **production** environment in GitHub (Settings → Environments → production) and add:

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | JSON service principal (see below) |
| `ACR_NAME` | Registry name (e.g. `onevoacr`) |
| `ACR_LOGIN_SERVER` | e.g. `onevoacr.azurecr.io` |
| `ACR_USERNAME` | `az acr credential show -n <acr> --query username -o tsv` |
| `ACR_PASSWORD` | ACR admin password |
| `VM_HOST` | VM public IP or DNS |
| `VM_USER` | SSH user (e.g. `azureuser` or `onevo`) |
| `VM_SSH_KEY` | Private key matching VM authorized_keys |
| `PRODUCTION_ENV` | Full multiline `.env` body (no ONEVO_*_IMAGE lines — CI appends those) |
| `BACKEND_PUBLIC_URL` | `https://api.yourdomain.example` — for smoke test + installer bake |

### Create service principal for GitHub

```bash
SUB=$(az account show --query id -o tsv)
az ad sp create-for-rbac \
  --name onevo-github-actions \
  --role contributor \
  --scopes /subscriptions/$SUB/resourceGroups/onevo-mvp-rg \
  --sdk-auth
```

Paste the JSON output into `AZURE_CREDENTIALS`. Grant the SP **AcrPush** on the registry:

```bash
ACR_ID=$(az acr show -n onevoacr --query id -o tsv)
SP_ID=$(az ad sp list --display-name onevo-github-actions --query "[0].id" -o tsv)
az role assignment create --assignee $SP_ID --role AcrPush --scope $ACR_ID
```

## 3. Pipelines

### CI — [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

Runs on every PR and push to `main`:

- `dotnet build` (backend)
- `pytest` (connector)
- `npm run build` (dashboard)
- Docker build (no push)

### CD — [`.github/workflows/deploy-mvp.yml`](../.github/workflows/deploy-mvp.yml)

Runs on push to `main` (with **production** environment approval if configured):

1. Build and push `onevo-backend`, `onevo-dashboard`, `onevo-cloud-ai` to ACR
2. Rsync repo to VM, write `.env`, run [`infra/mvp/deploy.sh`](../infra/mvp/deploy.sh)
3. Smoke test `GET /api/health`
4. **Windows job:** build installer EXE, upload artifact, copy to VM `connector/dist/`

Manual deploy: Actions → **Deploy MVP (Azure)** → Run workflow.

## 4. MVP launch checklist

- [ ] GPU VM + ACR provisioned, `vm-setup.sh` completed
- [ ] DNS: `app.*` → dashboard (port 4200 via nginx), `api.*` → backend (8081)
- [ ] TLS certificates (certbot)
- [ ] GitHub production secrets configured
- [ ] Push to `main` — deploy workflow green
- [ ] Login as Admin → **Get started** → installer download works
- [ ] Shop PC: run EXE, setup code, RTSP URLs
- [ ] Connector online on Setup page
- [ ] Test alert + email (`SMTP_ENABLE=true`)

## 5. Troubleshooting

| Issue | Fix |
|-------|-----|
| GPU quota denied | Use CPU VM or request quota increase; set `CLOUD_AI_DEVICE=cpu` in `.env` |
| ACR pull 401 on VM | Check `ACR_*` in `.env`; run `docker login` manually on VM |
| Installer 404 | Ensure `build-installer` job succeeded and EXE exists in `/opt/onevo/connector/dist/` |
| CORS errors | Set `CORS_ORIGINS=https://app.yourdomain.example` in `.env` |
| Deploy SSH fails | Verify `VM_SSH_KEY`, NSG allows SSH from GitHub Actions IPs (or use self-hosted runner in same VNet) |

## 6. Files reference

| Path | Purpose |
|------|---------|
| [`infra/mvp/provision-azure.sh`](../infra/mvp/provision-azure.sh) | Create RG, ACR, VM |
| [`infra/mvp/vm-setup.sh`](../infra/mvp/vm-setup.sh) | Docker, NVIDIA toolkit, nginx on VM |
| [`infra/mvp/deploy.sh`](../infra/mvp/deploy.sh) | Pull ACR images and restart compose |
| [`infra/mvp/nginx-host.conf`](../infra/mvp/nginx-host.conf) | Host TLS reverse proxy template |
| [`infra/mvp/.env.production.example`](../infra/mvp/.env.production.example) | Production env template |
| [`docker-compose.acr.yml`](../docker-compose.acr.yml) | Use pre-built images from ACR |

## Post-MVP

When outgrowing a single VM: Azure Database for PostgreSQL, Azure Cache for Redis, Blob Storage instead of MinIO, AKS or Container Apps with GPU node pool.
