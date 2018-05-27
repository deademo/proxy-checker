venv:
	python3 -m pip install virtualenv
	python3 -m virtualenv venv
	venv/bin/python -m pip install -r requirements.txt