# Speed / scale setup (target: ~30 requests per millisecond = 30,000 req/s)

Honest note: 30,000 req/s is possible ONLY for cached pages and static files (home page, images, PDFs).
Chat messages (/chat/send) hit MongoDB and the bot logic, so they scale with your hardware / Mongo plan.

## What was changed in the code
- `app.py`  : home page is rendered once and served from memory (ETag + 304 support) for new visitors;
              public cache headers so nginx / Cloudflare can cache it; long cache for static & catalog files.
- `db.py`   : Mongo connection pool (MONGO_POOL, default 100) + indexes on enquiries.created / status.
- `gunicorn.conf.py`  : multi-worker + threads production config.
- `nginx.conf.example`: nginx serves static files itself, caches home page, rate-limits /chat/.

## How to run (Linux server)
    pip install -r requirements.txt
    gunicorn -c gunicorn.conf.py app:app
    # install nginx, copy nginx.conf.example to /etc/nginx/conf.d/srj.conf, fix paths, `nginx -s reload`

## To really reach 30k req/s
1. Put Cloudflare (free) in front of your domain - cached pages/images never reach your server.
2. Use a server with 8+ CPU cores (or several servers behind a load balancer).
3. Use a paid MongoDB Atlas tier (M10+) - free tier cannot take thousands of chat writes per second.
4. Test with:  wrk -t8 -c1000 -d30s http://your-domain.com/   (or `hey`, `k6`)
