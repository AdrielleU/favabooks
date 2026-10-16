# --- build: frontend + wheel ---
# Python 3.12 (not bookworm's 3.11): hatch_build.py needs typing.override,
# and typing_extensions is not in Fava's build-system.requires.
FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-bookworm AS build
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
WORKDIR /src
COPY . .
ENV SETUPTOOLS_SCM_PRETEND_VERSION=1.30.16+favabooks
RUN pip install --no-cache-dir --root-user-action ignore build \
 && python -m build --wheel --outdir /wheels .

# --- runtime ---
FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir --root-user-action ignore \
      "$(ls /wheels/fava-*.whl)[excel]" beangulp smart_importer \
 && rm -rf /wheels
RUN useradd --create-home --uid 1000 fava
USER fava
RUN git config --global --add safe.directory '*'
WORKDIR /books
ENV FAVA_HOST=0.0.0.0 \
    FAVA_PORT=5000
EXPOSE 5000
# fava runs as PID 1 and has no SIGTERM handler; SIGINT stops it cleanly.
STOPSIGNAL SIGINT
CMD ["sh", "-c", "exec fava $LEDGERS"]
