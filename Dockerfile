FROM python:2-alpine
RUN apk add --no-cache bash gcc g++ swig python-dev postgresql-client \
                       postgresql-dev libffi-dev openssl-dev openldap-dev \
                       gettext libxml2 libxml2-dev libxslt libxslt-dev \
                       gpgme gpgme-dev libffi-dev py-psycopg2
COPY requirements.txt /requirements.txt
COPY testsuite/docker/test-config/test-requirements.txt /test-requirements.txt
COPY testsuite/docker/dev-config/dev-requirements.txt /dev-requirements.txt
RUN pip install --force-reinstall --ignore-installed --no-binary :all: egenix-mx-base
RUN pip install -r /requirements.txt
RUN pip install -r /test-requirements.txt
RUN pip install -r /dev-requirements.txt
RUN adduser -S cerebrum
