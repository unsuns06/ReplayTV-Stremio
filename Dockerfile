FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set default environment variables
ENV PORT=7860
ENV HOST=127.0.0.1

EXPOSE $PORT

CMD ["python", "run_server.py"]