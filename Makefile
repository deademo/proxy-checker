venv:
	python -m pip install virtualenv
	python -m virtualenv venv
	venv/bin/python -m pip install -r proxy_checker/requirements.txt

venv_win:
	python -m pip install virtualenv
	python -m virtualenv venv
	venv\\Scripts\\python.exe -m pip install -r proxy_checker/requirements.txt

build:
	docker build -t proxy_checker .

run:
	docker run -it proxy_checker /bin/sh

dev_win:
	docker run -v C:/py/proxy-checker/proxy_checker:/proxy_checker/ -it proxy_checker /bin/sh

test:
	cd proxy_checker && PYTHONPATH=. ../venv/bin/python -m unittest -v

cov:
	cd proxy_checker && PYTHONPATH=. ../venv/bin/python -m unittest -v

test_win:
	cd proxy_checker && PYTHONPATH=. ../venv/Scripts/python.exe -m unittest -v

cov_win:
	cd proxy_checker && PYTHONPATH=. ../venv/Scripts/python.exe -m nose --with-coverage --cover-package=.
