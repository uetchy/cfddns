start:
	docker-compose up -d --build

stop:
	docker-compose down

update: stop start

logs:
	docker-compose logs -f
