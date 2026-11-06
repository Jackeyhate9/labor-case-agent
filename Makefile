.PHONY: install dev api web test test-api test-web e2e self-check desktop-sidecar desktop-installer

install:
	python -m venv .venv
	.venv/Scripts/python -m pip install -e "apps/api[test,ocr]"
	cd apps/web && npm install

api:
	.venv/Scripts/python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000

web:
	cd apps/web && npm run dev

test: test-api test-web

test-api:
	.venv/Scripts/python -m pytest apps/api/tests -q

test-web:
	cd apps/web && npm test -- --run

e2e:
	cd apps/web && npm run test:e2e

self-check:
	powershell -NoProfile -Command "(Invoke-WebRequest http://localhost:8000/api/system/self-check).Content"

desktop-sidecar:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-sidecar.ps1

desktop-installer:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-desktop.ps1
