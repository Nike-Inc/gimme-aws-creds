init:
	pip3 install -r requirements_dev.txt

test:
	nosetests -vv tests
