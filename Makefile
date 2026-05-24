PYTHON ?= python
USER_ID ?=
CATEGORY ?= All_Beauty
LIMIT ?= 100

.PHONY: install test run-api run-streamlit docker-build docker-up docker-down embed-products build-taste-vector check-db migrate-dry-run migrate

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m compileall app src scripts tests client
	$(PYTHON) -m pytest tests

run-api:
	uvicorn app.api.main:app --reload

run-streamlit:
	streamlit run client/streamlit/streamlit_app.py

docker-build:
	docker compose build

docker-up:
	docker compose up

docker-down:
	docker compose down

embed-products:
	$(PYTHON) scripts/embed_products.py --limit $(LIMIT)

build-taste-vector:
	$(PYTHON) scripts/build_user_taste_vectors.py --user-id $(USER_ID) --category $(CATEGORY)

check-db:
	$(PYTHON) scripts/check_db_connection.py

migrate-dry-run:
	$(PYTHON) scripts/run_migrations.py --dry-run

migrate:
	$(PYTHON) scripts/run_migrations.py
