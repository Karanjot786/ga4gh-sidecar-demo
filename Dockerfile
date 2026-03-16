FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

COPY --from=builder /install /usr/local
COPY config.yaml /app/config.yaml

WORKDIR /app
ENV SIDECAR_CONFIG_PATH=/app/config.yaml

# Run as non-root
RUN useradd --create-home --shell /bin/bash sidecar
USER sidecar

EXPOSE 8080

CMD ["uvicorn", "ga4gh_sidecar.main:app", "--host", "0.0.0.0", "--port", "8080"]
