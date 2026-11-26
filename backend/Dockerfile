FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code/backend

COPY requirements.txt ./requirements.txt
RUN sed '/^nvidia-/d; /^triton==/d' requirements.txt > /tmp/requirements-cpu.txt \
    && python -m pip install --no-cache-dir --no-deps \
        --index-url https://download.pytorch.org/whl/cpu 'torch==2.8.0+cpu' \
    && python -m pip install --no-cache-dir -r /tmp/requirements-cpu.txt \
    && python -m pip check \
    && rm /tmp/requirements-cpu.txt \
    && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
COPY --chown=appuser:appuser alembic ./alembic

USER appuser
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
