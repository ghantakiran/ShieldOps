web: uvicorn shieldops.api.app:app --host 0.0.0.0 --port $PORT
worker: python -m shieldops.workers.main
migrate: alembic upgrade head
