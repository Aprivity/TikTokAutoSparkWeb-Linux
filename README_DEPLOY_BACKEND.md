# Ubuntu Backend Deployment

This backend is designed to run behind Nginx with PM2. It should listen only on `127.0.0.1:9844`, while Nginx proxies `/api/` to `http://127.0.0.1:9844/`.

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip chromium chromium-driver
```

If your distribution uses different package names, install a matching Chrome/Chromium and ChromeDriver pair.

## 2. Prepare project directory

```bash
cd /www/wwwroot/spark.aprivity.xyz
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

## 3. Configure environment

```bash
cp .env.example .env
nano .env
```

At minimum, change:

```bash
ADMIN_PASSWORD=your-strong-password
```

The backend refuses to start if `ADMIN_PASSWORD` is empty or left as a known default such as `123456` or `change-me-now`.

Common Linux values:

```bash
HOST=127.0.0.1
PORT=9844
CHROME_BIN=/usr/bin/chromium
CHROMEDRIVER_PATH=/usr/bin/chromedriver
HEADLESS=true
ALLOW_PUBLIC_BIND=false
CORS_ORIGINS=https://spark.aprivity.xyz,http://localhost:5173,http://127.0.0.1:5173
```

## 4. Start with PM2

```bash
pm2 start ecosystem.config.cjs
pm2 save
```

Useful commands:

```bash
pm2 logs spark-backend
pm2 restart spark-backend
pm2 status
```

## 5. Verify backend

```bash
curl http://127.0.0.1:9844/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "tiktok-auto-spark-backend"
}
```

## 6. Nginx proxy example

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:9844/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_connect_timeout 60s;
    proxy_read_timeout 60s;
}
```

Do not expose the backend directly to the public internet. Keep `HOST=127.0.0.1` unless you explicitly know why you need `ALLOW_PUBLIC_BIND=true`.
