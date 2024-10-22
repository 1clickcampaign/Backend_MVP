# how to run

### installing dependencies
```
pip install -r requirements.txt
```

### creating and activating the virtual environment
```
python -m venv .venv
.venv\Scripts\activate
```

### running the code locally (just uvicorn)
```
uvicorn app.main:app --reload
```

### testing dockerized app locally (run docker first)
```
docker build -t fastapi-backend .
docker run -p 8000:8000 --env-file .env fastapi-backend
```

### deploying to aws
push to main branch
