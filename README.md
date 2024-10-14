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

### deploying to aws
```
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 058264339376.dkr.ecr.us-east-2.amazonaws.com
docker build -t fastapi-backend .
docker tag fastapi-backend:latest 058264339376.dkr.ecr.us-east-2.amazonaws.com/datapull/fastapi-backend:latest
docker push 058264339376.dkr.ecr.us-east-2.amazonaws.com/datapull/fastapi-backend:latest
```
