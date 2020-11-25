FROM python:3.9-alpine

ARG TZ
ENV DEFAULT_TZ $TZ

# timezone
RUN apk upgrade --update \
  && apk add -U curl tzdata \
  && cp /usr/share/zoneinfo/${TZ} /etc/localtime \
  && apk del tzdata \
  && rm -rf \
  /var/cache/apk/*

# poetry
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python
ENV PATH /root/.poetry/bin:$PATH
ENV POETRY_VIRTUALENVS_IN_PROJECT true

# app
WORKDIR /app
COPY pyproject.toml poetry.lock /app/
RUN poetry install --no-dev
COPY ./src /app/src

CMD [".venv/bin/python", "src/update.py", "/domains"]