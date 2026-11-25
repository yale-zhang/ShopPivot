SHELL := /bin/bash
PYTHON ?= python3
RUFF ?= ruff
export PYTHONPATH := src:.
export SHOPPIVOT_ENV ?= dev

.PHONY: help doctor deps-check install up down init-db migrate seed demo serve dev test \
        test-unit test-contract test-modules test-integration test-e2e test-security \
        lint fmt typecheck verify clean web-install web-dev web-build web-test

deps-check:
	@$(PYTHON) -c "import alembic, fastapi, sqlalchemy, pydantic, pydantic_settings, openpyxl, jwt, yaml, celery, httpx" 2>/dev/null || \
		{ echo "缺少 Python 依赖（当前解释器：$$($(PYTHON) -c 'import sys; print(sys.executable)' 2>/dev/null)）"; \
		  echo "请先安装：$(PYTHON) -m pip install -e .[dev]（或 uv sync）"; \
		  exit 1; }

doctor: deps-check
	@echo "python: $$($(PYTHON) -c 'import sys; print(sys.executable, sys.version.split()[0])')"
	@$(PYTHON) -c "import alembic, fastapi, sqlalchemy; print('alembic', alembic.__version__, '| fastapi', fastapi.__version__, '| sqlalchemy', sqlalchemy.__version__)"

help:
	@echo "make doctor        检查 Python 解释器与依赖是否就绪"
	@echo "make up            启动 postgres/redis（可选，M0 默认 sqlite）"
	@echo "make init-db       建表（alembic upgrade head）"
	@echo "make seed          装配模块 + 灌入口径卡与演示数据"
	@echo "make demo          跑一次 S01 日报全链并打印 run_id / 报表路径"
	@echo "make serve         uvicorn 启动 API（127.0.0.1:8000）"
	@echo "make dev           一键起 API + 前端 dev（先 seed）"
	@echo "make test          全量后端测试"
	@echo "make verify        lint + typecheck + 全量测试 + 文档检查"
	@echo "make web-install   安装前端依赖"
	@echo "make web-dev       前端开发服务器（5173）"
	@echo "make web-build     前端生产构建"
	@echo "make web-test      前端单元测试"

install:
	$(PYTHON) -m pip install -e .[dev]

up:
	docker compose -f deploy/docker-compose.yml up -d postgres redis

down:
	docker compose -f deploy/docker-compose.yml down

init-db: deps-check
	$(PYTHON) -m alembic -c migrations/alembic.ini upgrade head

migrate: init-db

seed: init-db
	$(PYTHON) -m bootstrap.cli seed

demo: seed
	$(PYTHON) -m bootstrap.cli run-daily

serve: deps-check
	$(PYTHON) -m uvicorn bootstrap.api:app --host 127.0.0.1 --port 8000 --reload

dev: deps-check
	@bash scripts/dev.sh

test: deps-check
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit

test-contract:
	$(PYTHON) -m pytest tests/contract

test-modules:
	$(PYTHON) -m pytest tests/modules

test-integration:
	$(PYTHON) -m pytest tests/integration

test-e2e:
	$(PYTHON) -m pytest tests/e2e

test-security:
	$(PYTHON) -m pytest tests/security

lint:
	@if [ -x "$(RUFF)" ]; then \
		$(RUFF) check src modules tests scripts; \
		$(RUFF) format --check src modules tests scripts; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff check src modules tests scripts; \
		ruff format --check src modules tests scripts; \
	else \
		echo "ruff 未安装，回退 flake8（仅静态检查，不含格式）"; \
		$(PYTHON) -m flake8 --max-line-length=120 --extend-ignore=E203,W503,E501 \
			--exclude=.venv,node_modules,__pycache__,dist src modules tests scripts; \
	fi

fmt:
	$(RUFF) format src modules tests scripts
	$(RUFF) check --fix src modules tests scripts

typecheck:
	$(PYTHON) -m mypy

web-install:
	cd frontend && pnpm install

web-dev:
	cd frontend && pnpm dev

web-build:
	cd frontend && pnpm build

web-test: deps-check
	cd frontend && pnpm test

verify: lint typecheck test
	$(PYTHON) scripts/check_docs.py

clean:
	rm -rf storage/*.db storage/reports .pytest_cache .mypy_cache .ruff_cache
