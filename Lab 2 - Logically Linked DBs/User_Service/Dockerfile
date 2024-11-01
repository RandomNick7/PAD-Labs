# Using a base image with Python
FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache curl
RUN curl -L https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.34/grpc_health_probe-linux-amd64 -o /usr/local/bin/grpc_health_probe && \
    chmod +x /usr/local/bin/grpc_health_probe
COPY . .
RUN pip install -r requirements.txt
EXPOSE 9000
CMD ["python", "main.py"]