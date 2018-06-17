venv:
	python3 -m pip install virtualenv
	python3 -m virtualenv venv
	venv/bin/python -m pip install -r proxy_checker/requirements.txt

build:
	docker build -t proxy_checker .

run:
	docker run -it proxy_checker /bin/sh

dev_win:
	docker run -v C:/py/proxy-checker/proxy_checker:/proxy_checker/ -it proxy_checker /bin/sh
