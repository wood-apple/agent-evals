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
    && apt-get install -y --no-install-recommends ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_TOOL_DIR=/opt/uv-tools \
    UV_TOOL_BIN_DIR=/usr/local/bin \
    UV_LINK_MODE=copy
RUN uv tool install --python 3.13 hermes-agent==0.19.0

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

ENV EVALS_ROOT=/app \
    EVALS_WORKER=/app/worker/.venv/bin/evals \
    PORT=3000
EXPOSE 3000
CMD ["node", "--disable-warning=ExperimentalWarning", "api/dist/main.js"]
