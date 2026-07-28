# ONEVO MVP — Azure resources provisioned

Generated after Azure MCP / CLI provisioning. **Do not commit secrets** — fetch ACR passwords with `az acr credential show`.

## Created resources

| Resource | Value |
|----------|--------|
| Subscription | `6f55fbe2-e265-4592-ab26-ee66c639ba93` |
| Resource group | `onevo-mvp-rg` |
| ACR name | `onevoacrmvp` |
| ACR login server | `onevoacrmvp.azurecr.io` |
| VM name | `onevo-mvp-vm` |
| VM location | `australiaeast` (eastus had no GPU quota / capacity) |
| VM size | `Standard_D2s_v5` (CPU — request GPU quota for production AI) |
| VM public IP | `20.193.69.220` |
| SSH user | `azureuser` |

## GitHub Actions secrets (production environment)

Set these in GitHub → Settings → Environments → **production**:

| Secret | Value |
|--------|--------|
| `ACR_NAME` | `onevoacrmvp` |
| `ACR_LOGIN_SERVER` | `onevoacrmvp.azurecr.io` |
| `ACR_USERNAME` | `onevoacrmvp` |
| `ACR_PASSWORD` | Run: `az acr credential show -n onevoacrmvp --query passwords[0].value -o tsv` |
| `VM_HOST` | `20.193.69.220` |
| `VM_USER` | `azureuser` |
| `VM_SSH_KEY` | Contents of your private key (`~/.ssh/id_rsa`) used at VM create |
| `BACKEND_PUBLIC_URL` | `http://20.193.69.220:8081` until TLS/DNS configured |
| `PRODUCTION_ENV` | Copy from `infra/mvp/.env.production.example` — set secrets, `CLOUD_AI_DEVICE=cpu` |

Also create `AZURE_CREDENTIALS` service principal JSON (see [AZURE_MVP_DEPLOY.md](../../docs/AZURE_MVP_DEPLOY.md)).

## Next steps on the VM

```bash
ssh azureuser@20.193.69.220
git clone <your-github-repo-url> /opt/onevo
cd /opt/onevo
sudo ACR_LOGIN_SERVER=onevoacrmvp.azurecr.io bash infra/mvp/vm-setup.sh
cp infra/mvp/.env.production.example /opt/onevo/.env
# Edit .env — set CLOUD_AI_DEVICE=cpu, passwords, JWT, SMTP
```

After DNS/TLS: update `CORS_ORIGINS`, `DASHBOARD_BASE_URL`, `BACKEND_PUBLIC_URL`, and re-run installer build with HTTPS API URL.

## GPU quota (recommended for pilot)

Request **Standard NCASv3 T4 Family** quota in your preferred region, then resize or recreate VM as `Standard_NC4as_T4_v3` and set `CLOUD_AI_DEVICE=cuda`.

Azure portal: [Quota increase](https://aka.ms/ProdportalCRP/#blade/Microsoft_Azure_Capacity/UsageAndQuota.ReactView)

## Installer download

Unchanged: shops download the Windows EXE from the **dashboard** after login. The deploy pipeline copies the built EXE to `/opt/onevo/connector/dist/` on this VM.
