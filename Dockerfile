FROM python:3.13.9-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./
RUN echo "--- requirements.txt (build-time) ---" \
 && cat requirements.txt \
 && echo "--- end requirements.txt ---" \
 && (grep -n "^ollama==" requirements.txt || true)
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run.py"]
