start:
	docker-compose up -d --build

stop:
	docker-compose down --rmi local --remove-orphans

update: stop start

logs:
	docker-compose logs -f