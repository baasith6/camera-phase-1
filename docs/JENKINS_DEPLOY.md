# Jenkins CI/CD on Windows

Deploy ONEVO to the Azure MVP VM from your local Windows PC using the root [`Jenkinsfile`](../Jenkinsfile) and [`scripts/deploy-vm.ps1`](../scripts/deploy-vm.ps1).

## Why Jenkins here

- Builds the **Windows connector installer** on the same machine (Inno Setup + PyInstaller).
- SSH/SCP to the VM already works from your dev PC.
- Avoids GitHub Actions secret/path drift while the pilot is active.

## Prerequisites

1. [Jenkins LTS](https://www.jenkins.io/download/) installed on Windows.
2. **Git** and **OpenSSH client** (Windows 10+ optional feature or Git for Windows).
3. **.NET 8 SDK**, **Node.js 20**, **Python 3.11+** on the Jenkins agent (same PC). Set `ONEVO_PYTHON` in the Jenkinsfile to your Python exe — Jenkins service account often has no `python` on PATH.
4. **Inno Setup 6** + PyInstaller deps for connector installer (see [`connector/installer/INSTALL.md`](../connector/installer/INSTALL.md)).
5. SSH private key that can log in as `azureuser@20.193.69.220`. On Windows OpenSSH, use your **RSA** key (`id_rsa`) in Jenkins — explicit `-i` with `id_ed25519` often fails even when plain `ssh` works.

## Jenkins plugins

- Pipeline
- Git
- Credentials Binding
- SSH Agent (optional)

## Credentials (Jenkins → Manage Credentials)

| ID | Type | Value |
|----|------|--------|
| `onevo-vm-ssh-key` | SSH Username with private key | User `azureuser`, paste **RSA** private key (`id_rsa` contents, not ed25519) |

## Create the pipeline job

1. **New Item** → name `onevo-deploy` → **Pipeline**.
2. **Pipeline** → Definition: **Pipeline script from SCM**.
3. SCM: **Git**, repository URL, branch `azure-mvp-deploy` or `main`.
4. Script Path: `Jenkinsfile`.
5. Save → **Build with Parameters**.

### Parameters (defaults)

| Parameter | Default |
|-----------|---------|
| `VM_HOST` | `20.193.69.220` |
| `VM_USER` | `azureuser` |
| `BACKEND_URL` | `http://20.193.69.220:8081` |
| `SKIP_INSTALLER` | false |
| `SKIP_CI` | false |
| `USE_GPU` | false (CPU VM) |

## Manual deploy (without Jenkins)

From repo root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-vm.ps1 `
  -VmHost 20.193.69.220 `
  -BackendUrl http://20.193.69.220:8081
```

Skip installer rebuild:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-vm.ps1 -SkipInstaller
```

## Auto-trigger on git push

**Option A — Poll SCM** (simplest): In job config, **Build Triggers** → **Poll SCM** → `H/5 * * * *` (every 5 minutes).

**Option B — GitHub webhook**: Install **GitHub plugin**, add webhook pointing to `http://<your-jenkins>:8080/github-webhook/`.

## Pipeline stages

1. **CI** — `dotnet build`, `npm run build`, `pytest` (parallel).
2. **Deploy to VM** — tarball → SCP → extract under `/opt/onevo/app` → `docker compose build` + `up`.
3. **Smoke test** — `GET /api/health` and dashboard HTTP 200.

## VM layout (canonical)

| Path | Purpose |
|------|---------|
| `/opt/onevo/app/` | Git repo + docker-compose project |
| `/opt/onevo/app/.env` | Production secrets |
| `/opt/onevo/app/installer-site/` | Connector EXE served by backend |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| SSH permission denied | Re-check `onevo-vm-ssh-key` credential; deploy script copies the key with strict ACLs for OpenSSH on Windows |
| GPU compose error | Keep `USE_GPU=false` on CPU VM |
| Missing `ffmpeg.exe` | First build auto-downloads to `%ProgramData%\onevo\installer-tools\`; or run `scripts/ensure-installer-tools.ps1` once |
| Installer build fails | Install Inno Setup 6 + PyInstaller; run `scripts/build-installer.ps1` manually once |
| Backend unhealthy after deploy | SSH to VM: `cd /opt/onevo/app && docker compose logs backend --tail 50` |

## Related

- [`docs/AZURE_MVP_DEPLOY.md`](AZURE_MVP_DEPLOY.md) — Azure + GitHub Actions
- [`infra/mvp/deploy.sh`](../infra/mvp/deploy.sh) — VM-side deploy (ACR pull or local build)
