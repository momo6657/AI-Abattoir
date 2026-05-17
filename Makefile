.PHONY: up down seed test lint build clean

# Start all services
up:
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# Run seed script (register models + agents)
seed:
	docker-compose run --rm seed

# Run backend tests
test-backend:
	cd backend && pytest tests/ -v --tb=short

# Run frontend tests
test-frontend:
	cd frontend && npm run test

# Run all tests
test: test-backend test-frontend

# Lint backend
lint-backend:
	cd backend && ruff check .

# Lint frontend
lint-frontend:
	cd frontend && npm run lint

# Lint all
lint: lint-backend lint-frontend

# Build frontend
build:
	cd frontend && npm run build

# Clean up
clean:
	docker-compose down -v
	rm -f backend/test.db
	rm -rf frontend/.next frontend/node_modules

# View logs
logs:
	docker-compose logs -f

# Backend shell
shell-backend:
	docker-compose exec backend bash

# Database shell
shell-db:
	docker-compose exec db psql -U postgres -d ai_abattoir
