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
   - Alert appears on **Alerts** page
   - Email arrives at the store notification address (if `SMTP_ENABLE=true`)

## Shop PC technician

1. Run `ONEVO-Connector-Setup-*.exe` as Administrator.
2. Enter the **setup code** from ONEVO admin.
3. Enter **RTSP URL(s)** for each camera (semicolon-separated for multiple).
4. Wait for the Windows service to start — status UI: http://localhost:8099/

## Store manager (day-to-day)

1. Open the **landing page** URL provided by ONEVO and sign in.
2. Review **Alerts** (web + email for score ≥ 70).
3. Use **Setup & Zones** only if cameras need changes (Installer/Admin role).

## Troubleshooting

| Issue | Check |
|-------|--------|
| Installer download 404 | Build EXE: `connector/installer/build.ps1` → `connector/dist/` |
| No email alerts | `SMTP_ENABLE=true`, Gmail app password, store `notificationEmail` set |
| Manager sees no alerts | Store visibility not `Silent`; user role is Manager |
| Connector offline | Shop PC firewall, backend URL reachable, setup code not expired |
| Slow analysis | Enable GPU: `docker-compose.gpu.yml` |
