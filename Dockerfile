FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Atualiza pacotes do sistema com correção de segurança e remove ferramentas de build que não rodam em produção.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip uninstall -y setuptools wheel

COPY api ./api
COPY web ./web
COPY weights/agrofacil.onnx weights/agrofacil.json ./weights/

RUN useradd --create-home --uid 1000 agrofacil
USER agrofacil

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
