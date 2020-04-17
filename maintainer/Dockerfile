FROM python:3.7 AS build

WORKDIR /tmp

RUN pip install pipenv

COPY Pipfile .
COPY Pipfile.lock .

RUN pipenv install --system

COPY maintainer maintainer
COPY setup.py setup.py

RUN python setup.py install

ENTRYPOINT ["python", "maintainer/header_forwarder/h.py", "/mnt/relay-maintainer/.env"]
