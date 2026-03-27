# DEPLOY.md — AMIP Deployment Guide

## Architecture

```
Cloudflare Pages (free)          Contabo VPS (€7.50/mo)
┌─────────────────────┐          ┌──────────────────────────┐
│  React static build │          │  Caddy (reverse proxy)   │
│  Auto-deploys from  │  ──→──  │  FastAPI + uvicorn       │
│  GitHub push        │          │  DuckDB (~270 MB file)   │
└─────────────────────┘          │  Bluetooth poller        │
                                 │  Daily refresh           │
                                 └──────────────────────────┘
```

- **Frontend:** Cloudflare Pages watches the GitHub repo, auto-builds and deploys on push
- **Backend:** Contabo Cloud VPS 10 (4 vCPU, 8 GB RAM, 75 GB NVMe)
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
5. Restart the refresh service: `sudo systemctl restart amip-refresh`

### Database schema changes

Option A — run migration on VPS:
```bash
ssh amip
cd /opt/amip
python3 scripts/your_migration.py
sudo systemctl restart amip-api
```

Option B — replace the DB file (~270 MB):
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

### 1. Server provisioning (Contabo)

- Cloud VPS 10: 4 vCPU, 8 GB RAM, 75 GB NVMe
- Location: EU (Germany/Finland) — upgrade to Sydney later if needed
- OS: Ubuntu 24.04
- Note the IP address and root password from the provisioning email
- Contabo default user is `root`. We create an `amip` user below.

### 2. First login and user setup

```bash
# SSH in as root (using password from Contabo email)
ssh root@<VPS_IP>

# Create a non-root user
adduser amip --disabled-password --gecos ""
usermod -aG sudo amip
echo "amip ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/amip

# Set up SSH key auth
mkdir -p /home/amip/.ssh
# Paste your public key:
echo "ssh-ed25519 YOUR_PUBLIC_KEY_HERE" > /home/amip/.ssh/authorized_keys
chown -R amip:amip /home/amip/.ssh
chmod 700 /home/amip/.ssh && chmod 600 /home/amip/.ssh/authorized_keys

# Disable root SSH login and password auth
sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

### 3. System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git ufw
```

### 4. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

### 5. Install Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudflare.com/caddy/stable/deb/debian/gpg' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudflare.com/caddy/stable/deb/debian/caddy-stable.list' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

### 6. Clone and install

```bash
sudo mkdir -p /opt/amip
sudo chown amip:amip /opt/amip
git clone https://github.com/dougtan333/traffic-movement.git /opt/amip
cd /opt/amip
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 7. Environment variables

```bash
cat > /opt/amip/.env << 'EOF'
CORS_ORIGINS=https://yourdomain.com
AMIP_DEBUG=false
SERVO_SAVER_CONSUMER_ID=your_key_here
VIC_BLUETOOTH_API_KEY=your_key_here
EIA_API_KEY=your_key_here
EOF
```

### 8. Copy database and Parquet archives

```bash
# From your Mac:
scp db/amip.duckdb amip:/opt/amip/db/
scp -r db/archive/ amip:/opt/amip/db/archive/
```

This transfers ~270 MB (DuckDB) + ~410 MB (Parquet archives). Takes a few minutes.

### 9. Systemd services

Create three service files:

**`/etc/systemd/system/amip-api.service`**
```ini
[Unit]
Description=AMIP FastAPI
After=network.target

[Service]
User=amip
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
User=amip
WorkingDirectory=/opt/amip
ExecStart=/opt/amip/venv/bin/python scripts/poll_bluetooth.py --loop
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/opt/amip/.env

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/amip-refresh.service`**
```ini
[Unit]
Description=AMIP Daily Data Refresh
After=network.target

[Service]
User=amip
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

### 10. Caddy config

**`/etc/caddy/Caddyfile`**
```
yourdomain.com {
    reverse_proxy localhost:8000

    @api path /api/*
    header @api Cache-Control "public, max-age=60"
}
```

```bash
sudo systemctl restart caddy
```

### 11. Cloudflare Pages (frontend)

1. Go to Cloudflare Dashboard → Pages → Create a project
2. Connect your GitHub repo (`dougtan333/traffic-movement`)
3. Build settings:
   - Build command: `cd frontend && npm install && npm run build`
   - Output directory: `frontend/dist`
   - Environment variable: `VITE_API_URL=https://yourdomain.com`
4. Deploy — auto-deploys on every push to `main`

### 12. Cloudflare DNS

Point your domain to the Contabo VPS public IP:
- `A` record: `yourdomain.com` → `<VPS_IP>`
- Enable Cloudflare proxy (orange cloud) for DDoS + edge caching

---

## Monitoring

```bash
# Check service status
sudo systemctl status amip-api amip-bluetooth amip-refresh

# View logs
journalctl -u amip-api -f                    # API logs (live)
journalctl -u amip-bluetooth --since today   # Poller logs
journalctl -u amip-refresh --since today     # Refresh logs

# API health check
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Disk usage
du -sh /opt/amip/db/*
df -h /  # 75 GB NVMe total
```

---

## SSH shortcut

Add to `~/.ssh/config` on your Mac:
```
Host amip
    HostName <VPS_PUBLIC_IP>
    User amip
    IdentityFile ~/.ssh/id_ed25519
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
