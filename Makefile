PY := .venv/bin/python

test:
	$(PY) -m pytest -q

dev:
	.venv/bin/uvicorn app.main:app --reload --port 8000

content:
	$(PY) scripts/parse_content.py --subject 812 --subject 315 --subject 101

audio:
	$(PY) scripts/gen_audio.py

dist:
	$(PY) scripts/package.py

.PHONY: test dev content audio dist
