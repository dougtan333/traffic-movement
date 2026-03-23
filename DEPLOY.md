# DEPLOY.md — AMIP Deployment Guide

## Architecture

```
Cloudflare Pages (free)          Oracle Cloud ARM VPS (free)
┌─────────────────────┐          ┌──────────────────────────┐
│  React static build │          │  Caddy (reverse proxy)   │
│  Auto-deploys from  │  ──→──  │  FastAPI + uvicorn       │
│  GitHub push        │          │  DuckDB (47 MB file)     │
└─────────────────────┘          │  Bluetooth poller        │
                                 │  Daily refresh           │
                                 └──────────────────────────┘
```

- **Frontend:** Cloudflare Pages watches the GitHub repo, auto-builds and deploys on push
- **Backend:** Oracle Cloud Ampere A1 (4 ARM cores, 24 GB RAM, always free)
- **Proxy:** Caddy handles HTTPS (auto Let's Encrypt), rate limiting, response caching
- **Data:** DuckDB single file on disk, pollers write directly to it

---

## Day-to-day: making changes after deployment

### Frontend changes (React components, styling, charts, tabs)

1. Edit locally on your Mac, test with `npm run dev`
2. `git add . && git commit -m "description" && git push`
3. Cloudflare Pages auto-deploys — live in ~30 seconds
4. **No server touch needed**

### Backend changes (API endpoints, query logic, route files)

1. Edit locally, test against local DuckDB + API
2. `git push`
3. SSH into VPS and pull + restart:

```bash
ssh amip
cd /opt/amip
git pull
sudo systemctl restart amip-api
```

Takes ~5 seconds. The pollers don't need restarting unless you changed their code.

### New data source or ingestion script

1. Build and test locally
2. `git push`
3. On VPS: `git pull`
4. If it runs on a schedule, add it to `daily_refresh.py`
5. Restart the refresh service:

```bash
sudo systemctl restart amip-refresh
```

### Database schema changes (new tables, columns, summary structure)

Option A — run migration on VPS:
```bash
ssh amip
cd /opt/amip
python3 scripts/your_migration.py
sudo systemctl restart amip-api
```

Option B — replace the DB file (it's only 47 MB):
```bash
scp db/amip.duckdb amip:/opt/amip/db/amip.duckdb
ssh amip "sudo systemctl restart amip-api"
```

### Poller or refresh script changes

```bash
ssh amip
cd /opt/amip && git pull
sudo systemctl restart amip-bluetooth   # if poller code changed
sudo systemctl restart amip-refresh     # if daily_refresh.py changed
```

---

## Initial VPS setup (one-time)

### 1. Server provisioning (Oracle Cloud)

- Create Ampere A1 instance: 4 OCPU, 24 GB RAM, Ubuntu 22.04
- Reserve a static public IP
- Open ports 80, 443 in VCN security list
- SSH key auth (no password login)

### 2. System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3-pip git
```

### 3. Install Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudflare.com/caddy/stable/deb/debian/gpg' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudflare.com/caddy/stable/deb/debian/caddy-stable.list' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

### 4. Clone and install

```bash
sudo mkdir -p /opt/amip
sudo chown $USER:$USER /opt/amip
git clone https://github.com/dougtan333/traffic-movement.git /opt/amip
cd /opt/amip
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Environment variables

```bash
cat > /opt/amip/.env << 'EOF'
CORS_ORIGINS=https://yourdomain.com
AMIP_DEBUG=false
SERVO_SAVER_CONSUMER_ID=your_key_here
EOF
```

### 6. Copy database and archive

```bash
# From your Mac:
scp db/amip.duckdb amip:/opt/amip/db/
scp -r db/archive/ amip:/opt/amip/db/archive/
```

### 7. Systemd services

Create three service files:

**`/etc/systemd/system/amip-api.service`**
```ini
[Unit]
Description=AMIP FastAPI
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/amip
ExecStart=/opt/amip/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
EnvironmentFile=/opt/amip/.env

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/amip-bluetooth.service`**
```ini
[Unit]
Description=AMIP Bluetooth Speed Poller
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/amip
ExecStart=/opt/amip/venv/bin/python scripts/poll_bluetooth.py --loop
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/amip-refresh.service`**
```ini
[Unit]
Description=AMIP Daily Data Refresh
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/amip
ExecStart=/opt/amip/venv/bin/python scripts/daily_refresh.py --loop
Restart=always
RestartSec=60
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/opt/amip/.env

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now amip-api amip-bluetooth amip-refresh
```

### 8. Caddy config

**`/etc/caddy/Caddyfile`**
```
yourdomain.com {
    reverse_proxy localhost:8000

    # Cache API responses for 60 seconds
    @api path /api/*
    header @api Cache-Control "public, max-age=60"

    # Rate limit: 60 requests per minute per IP
    rate_limit {
        zone api_limit {
            key {remote_host}
            events 60
            window 1m
        }
    }
}
```

```bash
sudo systemctl restart caddy
```

### 9. Cloudflare Pages (frontend)

1. Go to Cloudflare Dashboard → Pages → Create a project
2. Connect your GitHub repo (`dougtan333/traffic-movement`)
3. Build settings:
   - Build command: `cd frontend && npm install && npm run build`
   - Output directory: `frontend/dist`
   - Environment variable: `VITE_API_URL=https://yourdomain.com`
4. Deploy — auto-deploys on every push to `main`

### 10. Cloudflare DNS

Point your domain to the Oracle VPS public IP:
- `A` record: `yourdomain.com` → `<VPS_IP>`
- Enable Cloudflare proxy (orange cloud) for DDoS + edge caching

---

## Monitoring

```bash
# Check service status
sudo systemctl status amip-api amip-bluetooth amip-refresh

# View logs
journalctl -u amip-api -f              # API logs (live)
journalctl -u amip-bluetooth --since today  # Poller logs
journalctl -u amip-refresh --since today    # Refresh logs

# API health check
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Database freshness
curl -s http://localhost:8000/api/health

# Disk usage
du -sh /opt/amip/db/*
```

---

## SSH shortcut

Add to `~/.ssh/config` on your Mac:
```
Host amip
    HostName <VPS_PUBLIC_IP>
    User ubuntu
    IdentityFile ~/.ssh/oracle_amip
```

Then: `ssh amip` gets you in.

---

## Quick reference

| Task | Command |
|---|---|
| Deploy frontend | `git push` (auto-deploys via Cloudflare Pages) |
| Deploy backend | `ssh amip "cd /opt/amip && git pull && sudo systemctl restart amip-api"` |
| View API logs | `ssh amip "journalctl -u amip-api -n 50"` |
| Restart everything | `ssh amip "sudo systemctl restart amip-api amip-bluetooth amip-refresh"` |
| Check health | `curl -s https://yourdomain.com/api/health` |
| Copy DB to server | `scp db/amip.duckdb amip:/opt/amip/db/` |
| Backup DB from server | `scp amip:/opt/amip/db/amip.duckdb ./db/amip_vps_backup.duckdb` |
