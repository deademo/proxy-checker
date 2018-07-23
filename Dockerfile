FROM alpine:3.7

RUN apk add --no-cache python3 alpine-sdk libxml2 libxml2-dev libxslt-dev python3-dev postgresql-dev

ADD proxy_checker/requirements.txt /proxy_checker/proxy_checker/requirements.txt
WORKDIR /proxy_checker/

RUN python3 -m pip install --upgrade pip && python3 -m pip install virtualenv && python3 -m virtualenv venv 
RUN venv/bin/python -m pip install -r proxy_checker/requirements.txt

RUN apk add mariadb-dev --no-cache
RUN venv/bin/python -m pip install mysqlclient

ADD ./proxy_checker/ /proxy_checker/proxy_checker/
ADD ./Makefile /proxy_checker/Makefile
