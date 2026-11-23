FROM node:22-bookworm-slim AS ui
WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM node:22-bookworm-slim AS api
WORKDIR /app/api
COPY api/package.json api/package-lock.json ./
RUN npm ci
COPY api/ ./
RUN npm run build && npm prune --omit=dev

FROM node:22-bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git python3 sudo \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_TOOL_DIR=/opt/uv-tools \
    UV_TOOL_BIN_DIR=/usr/local/bin \
    UV_LINK_MODE=copy
ARG HERMES_COMMIT=0f602c5f6f18615632535251d62a2db74ce93b69
RUN git init -q /opt/hermes \
    && cd /opt/hermes \
    && git fetch -q --depth 1 https://github.com/NousResearch/hermes-agent.git "$HERMES_COMMIT" \
    && git checkout -q FETCH_HEAD \
    && uv sync --frozen --python 3.14 --extra anthropic --extra google \
    && ln -s /opt/hermes/.venv/bin/hermes /usr/local/bin/hermes

WORKDIR /app
COPY worker/pyproject.toml worker/uv.lock worker/.python-version worker/
RUN cd worker && uv sync --frozen --no-dev --no-install-project
COPY worker/ worker/
RUN cd worker && uv sync --frozen --no-dev
COPY tasks/ tasks/
COPY skills/ skills/
COPY configs/ configs/
COPY judge-validation/ judge-validation/
COPY --from=api /app/api /app/api
COPY --from=ui /app/ui/dist /app/ui/dist

RUN groupadd agent \
    && useradd --no-create-home --gid agent --shell /usr/sbin/nologin agent \
    && usermod -aG agent node \
    && echo 'node ALL=(agent) NOPASSWD: /usr/bin/env' > /etc/sudoers.d/evals-agent \
    && chmod 0440 /etc/sudoers.d/evals-agent \
    && mkdir -p /app/results /tmp/evals-trials \
    && chown -R node:node /app/results /tmp/evals-trials \
    && chmod 0711 /tmp/evals-trials \
    && chown root:node /app \
    && chmod 0750 /app
USER node

ENV EVALS_AGENT_USER=agent \
    EVALS_TRIALS_DIR=/tmp/evals-trials \
    EVALS_ROOT=/app \
    EVALS_WORKER=/app/worker/.venv/bin/evals \
    PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "umask 002 && exec node --disable-warning=ExperimentalWarning api/dist/main.js"]
