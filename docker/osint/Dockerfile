# VAJRA OSINT aggregator — Dockerfile.
#
# Lives in crpf-sentinel (docker/osint/) and builds the EXTERNAL vajra-osint
# repo WITHOUT modifying a single file in it. Compose builds it with the
# parent directory as context (siblings: crpf-sentinel/ and vajra-osint/):
#
#   context:   ..
#   dockerfile: crpf-sentinel/docker/osint/Dockerfile
#
# The API layer (api.py) only needs requirements.txt — no spaCy model.

FROM python:3.11-slim

WORKDIR /app

COPY vajra-osint/ ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]