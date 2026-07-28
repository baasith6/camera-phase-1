# Managed pilot — per-store onboarding checklist

Use this after deploying the stack (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`).

## Entry URL

Share your production dashboard origin with stores (for example `https://dashboard.your-domain.example/`).

- **Public landing** (`/`) — product overview and sign-in link for staff
- **Staff sign-in** (`/login`) — Admin, Manager, and Installer accounts
- **Get started** (`/app/get-started`) — step-by-step checklist after login (installer download, setup code, cameras, connector status)

## Pre-launch ops checklist

Before onboarding the first real store:

1. Deploy with [`docker-compose.prod.yml`](../docker-compose.prod.yml) behind HTTPS
2. Set `.env`: strong JWT secret, `SMTP_ENABLE=true`, Gmail app password, `ALERT_VISIBILITY_MODE=ManagerOnly` (recommended)
3. Build the Windows installer: [`scripts/build-installer.ps1`](../scripts/build-installer.ps1) → EXE in `connector/dist/`
4. Verify `GET /api/connectors/installer` returns 200 when logged in as Admin
5. Run one end-to-end test: store → user → setup code → EXE on shop PC → RTSP → zones → alert + email

## ONEVO admin (per store)

1. Open the **landing page** and sign in as **Admin** (`admin@onevo.local` or your seeded admin).
2. Open **Get started** or **Admin** in the sidebar.
3. **Create store** — name, Gmail notification address, alert visibility (`ManagerOnly` recommended).
4. **Create manager user** — assign to the store; share email + password securely.
5. **Download Windows installer** — send `ONEVO-Connector-Setup-*.exe` to the shop PC.
6. **Generate setup code** for the store — send the code to the shop tech (expires in 24h).
7. Open **Cameras & zones** for the store — draw Shelf, HighValue, Checkout, Exit zones as needed.
8. After shop PC install: confirm connector shows **Installed · Online** on Setup & Zones or Get started.
9. Trigger a test alert with real retail footage (not synthetic MP4) and confirm:
   - Clip appears on **Clips** page with analysis status and AI events
   - Alert appears on **Alerts** page (score ≥ 40)
   - Email arrives at the store notification address (if `SMTP_ENABLE=true`, score ≥ 70)

## Clips vs alerts

| Page | What it shows |
|------|----------------|
| **Clips** (`/app/clips`) | Every uploaded video — status, AI events, risk score, playable video |
| **Alerts** (`/app/alerts`) | Only clips where risk score ≥ **40** |

**Test MP4 / synthetic video:** validates motion → upload → cloud-ai plumbing. It is **not** labeled theft. Such clips often show **Analyzed** with **0 AI events** and **no alert** — that is expected. Use **real retail CCTV footage with visible shoppers** for meaningful alerts.

**Theft MP4 on shop PC:** motion-based cuts (default 10s before + 10s after) may miss the actual theft moment. On http://localhost:8099 use **Upload full source file** to send the entire MP4 for analysis, or widen pre/post to 30/30 under **Clip window**.

### Connector admin (shop PC)

Open http://localhost:8099 after install:

- **Pause monitoring** — stop new clips without stopping the service
- **Clear local clips** — delete cached files and cancel pending uploads (frees disk)
- **Upload full source file** — upload the whole configured MP4 (best for theft test footage)
- **Clip window** — tune pre-roll / post-roll / cooldown for motion cuts

Delete uploaded test clips from dashboard **Clips** (Admin/Manager → Delete).

### Verify cloud-ai (ops)

On the Azure VM:

```bash
ssh azureuser@<VM_IP>
cd /opt/onevo/app
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs cloud-ai --tail 50
docker compose exec redis redis-cli LLEN onevo:clip-jobs
docker compose exec redis redis-cli LLEN onevo:clip-jobs:failed
```

Healthy: logs show `[cloud-ai] processing clip <uuid>` and queue depth **0**. Admins can also check **Health** → **Analysis pipeline** in the dashboard.

## Shop PC technician

1. Run `ONEVO-Connector-Setup-*.exe` as Administrator.
2. Enter the **setup code** from ONEVO admin.
3. Enter **RTSP URL(s)** for each camera (semicolon-separated for multiple).
4. Wait for the Windows service to start — status UI: http://localhost:8099/

## Store manager (day-to-day)

1. Open the **landing page** URL provided by ONEVO and sign in.
2. Review **Clips** to see all uploaded video and AI analysis (events + risk score).
3. Review **Alerts** (web + email for score ≥ 70).
4. Use **Setup & Zones** only if cameras need changes (Installer/Admin role).

## Troubleshooting

| Issue | Check |
|-------|--------|
| Installer download 404 | Build EXE: `connector/installer/build.ps1` → `connector/dist/` |
| No email alerts | `SMTP_ENABLE=true`, Gmail app password, store `notificationEmail` set |
| Manager sees no alerts | Store visibility not `Silent`; user role is Manager |
| Connector offline | Shop PC firewall, backend URL reachable, setup code not expired |
| Clip upload timeout (`:9000`) | Azure NSG must allow port **9000**; `S3_PUBLIC_ENDPOINT=http://<VM_IP>:9000`; test with `Test-NetConnection <VM_IP> -Port 9000` from shop PC |
| `disk_critical` on connector status | Free C: drive space (>10% free); clear `C:\ProgramData\ONEVO\Connector\data\clips\` after failed test uploads |
| Slow analysis | Enable GPU: `docker-compose.gpu.yml` |
| Clips show 0 AI events | Test/synthetic MP4 has no people — use real retail footage for alerts |
| No alert but clip analyzed | Risk score below 40 — check **Clips** detail page; try **Upload full source file** for theft MP4 |
| Wrong clip segment from MP4 | Motion trigger fired at wrong time — use **Upload full source file** or increase pre/post to 30s |
