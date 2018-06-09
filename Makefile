venv:
	python3 -m pip install virtualenv
	python3 -m virtualenv venv
	venv/bin/python -m pip install -r proxy_checker/requirements.txt

docker:
	docker build -t proxy_checker .
	docker run -it proxy_checker /bin/sh
