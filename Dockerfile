FROM python:3.13-slim

RUN adduser -u 65534 -D -H nobody

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/
COPY config.yaml.template /app/config.yaml

VOLUME ["/data"]
ENV DATA_DIR=/data
USER nobody

EXPOSE 5000

CMD ["python", "/app/src/web.py"]
