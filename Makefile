venv:
	python -m pip install virtualenv
	python -m virtualenv -p python3 venv
	venv/bin/python -m pip install -r proxy_checker/requirements.txt

venv_win:
	python -m pip install virtualenv
	python -m virtualenv venv
	venv\\Scripts\\python.exe -m pip install -r proxy_checker/requirements.txt

build:
	docker build -t deademo/proxy_checker .

push:
	docker push deademo/proxy_checker

run:
	docker-compose up

run_scraper:
	PYTHONPATH=. SCRAPY_SETTINGS_MODULE=proxy_scraper.settings venv/bin/python -m scrapy runspider proxy_scraper/spiders/free_proxy_list_net.py
	PYTHONPATH=. SCRAPY_SETTINGS_MODULE=proxy_scraper.settings venv/bin/python -m scrapy runspider proxy_scraper/spiders/spys_one.py

clean_docker:
	docker-compose kill
	docker-compose down

remove_db:
	rm -rf proxy_checker_data

restart: clean_docker run

enter:
	docker run -it deademo/proxy_checker /bin/sh

dev_win:
	docker run -v C:/py/proxy-checker:/proxy_checker/ -v /proxy_checker/venv -it proxy_checker /bin/sh

test: venv only_test

only_test:
	cd proxy_checker && PYTHONPATH=. ../venv/bin/python -m unittest -v

cov: venv only_cov

only_cov:
	cd proxy_checker && PYTHONPATH=. ../venv/bin/python -m nose tests/test_*.py --with-coverage --cover-package=.


test_win:
	cd proxy_checker && PYTHONPATH=. ../venv/Scripts/python.exe -m unittest -v

cov_win:
	cd proxy_checker && PYTHONPATH=. ../venv/Scripts/python.exe -m nose --with-coverage --cover-package=.

.PHONY: venv
