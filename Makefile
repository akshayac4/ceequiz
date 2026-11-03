.PHONY: up down build logs migrate makemigrations test seed shell createsuperuser collectstatic

DEV = -f docker-compose.yml -f docker-compose.dev.yml

up:
	docker compose $(DEV) up -d

down:
	docker compose $(DEV) down

build:
	docker compose $(DEV) build

logs:
	docker compose logs -f web

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

test:
	docker compose exec web python manage.py test

seed:
	docker compose exec web python manage.py seed_data

shell:
	docker compose exec web python manage.py shell

createsuperuser:
	docker compose exec web python manage.py createsuperuser

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput
