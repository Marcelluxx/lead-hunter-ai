FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --uid 10001 leadhunter
WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chown -R leadhunter:leadhunter /app
USER leadhunter

EXPOSE 8000
CMD ["uvicorn", "src.server:create_server_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
