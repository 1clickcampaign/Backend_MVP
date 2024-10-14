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
docker-compose up --build
```
