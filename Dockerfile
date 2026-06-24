FROM python:3.10-slim
WORKDIR /app
COPY main.py .
copy tracker.py .
CMD ["python", "-u", "main.py"]
