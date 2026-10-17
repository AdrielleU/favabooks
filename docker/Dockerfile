# --- build: frontend + wheel ---
# Every Python package in the image is the exact version (and hash) in
# uv.lock, the same ones CI tests; --locked fails the build if uv.lock is
# out of date with pyproject.toml. Update them with `make update-constraints`.
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM node:24-trixie-slim AS node
FROM python:3.14-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
WORKDIR /src
COPY . .
# .git isn't in the build context, so the version comes in as a build arg
# (PEP 440, without the leading v of the git tag), e.g. VERSION=0.1.0.
ARG VERSION=0.0.0+dev
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
RUN uv export --locked --no-dev --extra excel --no-emit-project \
      --output-file /wheels/requirements.txt \
 && uv build --wheel --out-dir /wheels .

# --- runtime ---
FROM python:3.14-slim-trixie
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir --root-user-action ignore --require-hashes \
      -r /wheels/requirements.txt \
 && pip install --no-cache-dir --root-user-action ignore --no-deps \
      /wheels/fava-*.whl \
 && pip check \
 && rm -rf /wheels
RUN useradd --create-home --uid 1000 fava \
 && mkdir /books && chown fava:fava /books
# Starter books, copied on first run (see entrypoint.sh)
COPY ledger-starter /opt/favabooks/ledger-starter
COPY ledger-personal /opt/favabooks/ledger-personal
COPY ledger-template /opt/favabooks/ledger-template
COPY ledger-ai /opt/favabooks/ledger-ai
COPY docker/entrypoint.sh /usr/local/bin/favabooks-entrypoint
COPY docker/new-books.sh /usr/local/bin/favabooks-new
USER fava
RUN git config --global --add safe.directory '*'
WORKDIR /books
ENV FAVA_HOST=0.0.0.0 \
    FAVA_PORT=5000 \
    FAVABOOKS_DOCKER=1
EXPOSE 5000
# fava runs as PID 1 and has no SIGTERM handler; SIGINT stops it cleanly.
STOPSIGNAL SIGINT
CMD ["favabooks-entrypoint"]
