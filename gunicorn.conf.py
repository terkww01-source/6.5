# gunicorn.conf.py
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
workers = 1
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
timeout = 120
loglevel = "info"
