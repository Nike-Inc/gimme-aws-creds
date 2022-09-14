init:
	pip3 install -r requirements_dev.txt

docker-build:
	docker build -t gimme-aws-creds .

test: docker-build
	pytest -v tests
