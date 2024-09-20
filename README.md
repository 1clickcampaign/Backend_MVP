# how to activate

### creating and activating the virtual environment
```
python -m venv .venv
.venv\Scripts\activate
```

### running the code
```
docker run -d -p 6379:6379 redis
celery -A celery_worker.celery_app worker --loglevel=info
uvicorn app.main:app --reload
```
