FROM alpine:3.7

RUN apk add --no-cache python3 alpine-sdk libxml2 libxml2-dev libxslt-dev python3-dev mariadb-dev libffi-dev

ADD proxy_checker/requirements.txt /proxy_checker/proxy_checker/requirements.txt
WORKDIR /proxy_checker/

RUN python3 -m pip install --upgrade pip && python3 -m pip install virtualenv && python3 -m virtualenv venv 
RUN venv/bin/python -m pip install -r proxy_checker/requirements.txt

COPY ./proxy_checker/ /proxy_checker/proxy_checker/
COPY ./Makefile /proxy_checker/Makefile

ENTRYPOINT ["/proxy_checker/venv/bin/python", "/proxy_checker/proxy_checker/check_file.py"]
CMD []
