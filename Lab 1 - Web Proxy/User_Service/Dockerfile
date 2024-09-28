# Using a base image with Python
FROM python:3.12-alpine
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 9000
CMD ["python", "main.py"]