# Run:  gunicorn -c gunicorn.conf.py app:app
import multiprocessing, os
# Render (and most free hosts) give you a PORT env var and want the app on 0.0.0.0.
# Locally (behind your own nginx) it still falls back to 127.0.0.1:8000 like before.
bind = "0.0.0.0:" + os.getenv("PORT", "8000") if os.getenv("PORT") else "127.0.0.1:8000"
# Render's free instance has only ~512MB RAM / 0.1 CPU - fewer workers/threads avoid out-of-memory restarts.
workers = int(os.getenv("WEB_WORKERS", 1 if os.getenv("PORT") else multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv("WEB_THREADS", 4 if os.getenv("PORT") else 8))
worker_class = "gthread"                                  # threads = good for Mongo / network waits
worker_connections = 1000
backlog = 4096
keepalive = 30
timeout = 60
graceful_timeout = 30
max_requests = 20000                                      # recycle workers to avoid memory creep
max_requests_jitter = 2000
preload_app = True                                        # load code once, share memory between workers
accesslog = None                                          # logging every hit costs speed
errorlog = "-"
