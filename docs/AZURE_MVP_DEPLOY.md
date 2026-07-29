# Azure MVP deployment runbook

Deploy ONEVO to a **single GPU Azure VM** with **Docker Compose**, built and released by **GitHub Actions**.

## Architecture

| Component | Where it runs |
|-----------|----------------|
| Backend, dashboard, cloud-ai, Postgres, Redis, MinIO | Azure GPU VM (Docker Compose) |
| Windows connector | **Shop PCs** — downloaded from dashboard after login |
| CI/CD | GitHub Actions or **Jenkins** → ACR or VM build → SSH deploy to VM |

Shop staff download `ONEVO-Connector-Setup-*.exe` from **Get started / Admin / Setup** in the dashboard. The backend serves the file from `/opt/onevo/app/installer-site/` on the VM (mounted into the backend container). The connector service itself does **not** run in Azure.

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
git clone <your-repo-url> /opt/onevo/app
cd /opt/onevo/app
sudo ACR_LOGIN_SERVER=<acr>.azurecr.io bash infra/mvp/vm-setup.sh
```

Edit `/etc/nginx/sites-available/onevo` — replace `YOUR_APP_DOMAIN` / `YOUR_API_DOMAIN`, reload nginx, then:

```bash
sudo certbot --nginx -d app.yourdomain.example -d api.yourdomain.example
```

Copy and fill secrets:

```bash
cp infra/mvp/.env.production.example /opt/onevo/app/.env
nano /opt/onevo/app/.env
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
- [ ] Shop PC: `Test-NetConnection <VM_IP> -Port 9000` succeeds (MinIO clip uploads)
- [ ] Connector online on Setup page
- [ ] Test alert + email (`SMTP_ENABLE=true`)
- [ ] Cloud-ai YOLOE prompts loaded (see section 4b below)

## 4b. Verify cloud-ai / YOLOE prompts

The `cloud-ai` worker uses **YOLOE** open-vocabulary prompts baked into [`cloud-ai/app/detector.py`](../cloud-ai/app/detector.py) unless `CLOUD_AI_YOLOE_PROMPTS` is set in `.env`.

**Default (recommended):** leave `CLOUD_AI_YOLOE_PROMPTS` empty — 12 prompt phrases including jacket concealment (`concealment` cue).

| Prompt phrase | Production cue | Old eval JSON cue |
|---------------|------------------|-------------------|
| person hiding item inside jacket | `concealment` | `open_bag` |
| person putting object under clothing | `concealment` | `open_bag` |
| hand inside jacket | `concealment` | `open_bag` |
| All other 9 prompts | same | same |

[`cloud-ai/eval/results_jacket_prompts.json`](../cloud-ai/eval/results_jacket_prompts.json) is a **local eval artifact**, not read at runtime. Re-run `python -m eval.run_jacket_test` after prompt changes to refresh it.

**On the VM after deploy:**

```bash
cd /opt/onevo/app
docker logs app-cloud-ai-1 --tail 30
# Expect: "YOLOE prompts (12): person, backpack, ..." and no repeated Redis socket timeouts

docker exec app-cloud-ai-1 python -c "from app.detector import DEFAULT_YOLOE_PROMPTS; print(len(DEFAULT_YOLOE_PROMPTS))"
# Expect: 12
```

**End-to-end:** upload a clip from the connector → `docker logs app-cloud-ai-1` shows `processing clip ...` → alert in dashboard if score ≥ 70.

## 5. Troubleshooting

| Issue | Fix |
|-------|-----|
| GPU quota denied | Use CPU VM or request quota increase; set `CLOUD_AI_DEVICE=cpu` in `.env` |
| ACR pull 401 on VM | Check `ACR_*` in `.env`; run `docker login` manually on VM |
| Installer 404 | Ensure `build-installer` job succeeded and EXE exists in `/opt/onevo/app/installer-site/` |
| CORS errors | Set `CORS_ORIGINS=https://app.yourdomain.example` in `.env` |
| Deploy SSH fails | Verify `VM_SSH_KEY`, NSG allows SSH from GitHub Actions IPs (or use self-hosted runner in same VNet) |
| Clip upload timeout (`:9000`) | NSG must allow **9000**; set `S3_PUBLIC_ENDPOINT=http://<VM_IP>:9000` in `.env`; test `curl http://<VM_IP>:9000/minio/health/live` from shop PC |
| Connector `disk_critical` on shop PC | Free C: drive space; clear `%ProgramData%\ONEVO\Connector\data\clips` |
| Cloud-ai `Timeout reading from socket` | Fixed in cloud-ai worker (Redis `socket_timeout=None`); redeploy cloud-ai image |
| YOLOE prompts not as expected | Check startup log for prompt list; override via `CLOUD_AI_YOLOE_PROMPTS` only if needed |

## 6. Files reference

| Path | Purpose |
|------|---------|
| [`infra/mvp/provision-azure.sh`](../infra/mvp/provision-azure.sh) | Create RG, ACR, VM |
| [`infra/mvp/vm-setup.sh`](../infra/mvp/vm-setup.sh) | Docker, NVIDIA toolkit, nginx on VM |
| [`infra/mvp/deploy.sh`](../infra/mvp/deploy.sh) | Pull ACR images or local build; restart compose |
| [`scripts/deploy-vm.ps1`](../scripts/deploy-vm.ps1) | Jenkins / manual deploy from Windows |
| [`Jenkinsfile`](../Jenkinsfile) | Jenkins pipeline definition |
| [`docs/JENKINS_DEPLOY.md`](JENKINS_DEPLOY.md) | Jenkins setup on Windows |
| [`infra/mvp/nginx-host.conf`](../infra/mvp/nginx-host.conf) | Host TLS reverse proxy template |
| [`infra/mvp/.env.production.example`](../infra/mvp/.env.production.example) | Production env template |
| [`docker-compose.acr.yml`](../docker-compose.acr.yml) | Use pre-built images from ACR |

## Post-MVP

When outgrowing a single VM: Azure Database for PostgreSQL, Azure Cache for Redis, Blob Storage instead of MinIO, AKS or Container Apps with GPU node pool.
