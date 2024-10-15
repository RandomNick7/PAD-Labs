import os
import grpc
import requests
import logging
import signal
import atexit
import psycopg2
import jwt
from time import sleep
from concurrent import futures
from consul import Consul

import user_routes_pb2 as pb2
import user_routes_pb2_grpc as pb2_grpc
import health_pb2 as hpb2
import health_pb2_grpc as hpb2_grpc


def generate_token(target_user):
    """Generates a JWT token given a user"""
    secret_key = os.getenv('JWT_SECRET')
    payload = {
        "user_id": target_user[0],
        "username": target_user[1]
    }
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token


class HealthService(hpb2_grpc.HealthServicer):
    def Check(self, request, context):
        return hpb2.HealthCheckResponse(status = hpb2.HealthCheckResponse.SERVING)


class UserService(pb2_grpc.UserRoutesServicer):
    def tryLogin(self, request, context):
        """Provides a JWT auth token and creates new users

        New users are created only if username doesn't already exist in the DB
        Existing users must send a request with matching user/pass to receive a JWT
        """
        result = {}
        logger.info("Request received!")
        
        query = "SELECT username, password FROM user_credentials WHERE username=%s"
        cursor.execute(query, (request.username,))
        target_user = cursor.fetchone()
        
        if request.newAccount:
            if target_user is None:
                query = "INSERT INTO user_credentials (username, password) VALUES (%s, %s) RETURNING id"
                cursor.execute(query, (request.username, request.password))
                logger.info("User Added!")

                new_id = cursor.fetchone()[0]
                token = generate_token((new_id, request.username))
                result = {"status": 200, "token": token}
            else:
                # Conflict - User already exists!
                result = {"status": 409}

        else:
            if target_user:
                logger.info("User Found!")
                token = generate_token(target_user)
                result = {"status": 200, "token": token}
            else:
                # Credential mismatch - User Not Found!
                result = {"status": 404}

        sleep(2.5)

        return pb2.LoginConfirm(**result)


def registerSelf():
    service_definition = {
        "ID": INSTANCE_ID,
        "Name": f"user-service-{INSTANCE_ID}"
    }

    response = requests.put(f"http://{consul_addr}:{consul_port}/v1/agent/service/register", json=service_definition)

    if response.status_code == 200:
        logger.info("Registered a User Service successfully!")
    else:
        logger.info("Error registering service!")


def deregisterSelf():
    consul.agent.service.deregister(INSTANCE_ID)


def addAllServicers(server):
    pb2_grpc.add_UserRoutesServicer_to_server(UserService(), server)
    hpb2_grpc.add_HealthServicer_to_server(HealthService(), server)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers = 1))
    addAllServicers(server)

    server.add_insecure_port("[::]:9000")
    server.start()

    logger.info("Server up and running!")
    server.wait_for_termination()


def check_db_tables():
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'user_data'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE user_data")

    cursor.execute("CREATE TABLE IF NOT EXISTS user_credentials\
        (id SERIAL PRIMARY KEY, username TEXT, password TEXT)")


def signalHandler(signal, frame):
    deregisterSelf()
    logger.info("Deregistered a User Service")
    exit(0)


if __name__ == '__main__':
    consul_addr = "consul"
    consul_port = 8500
    INSTANCE_ID = os.environ.get("HOSTNAME")

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    conn.autocommit = True
    cursor = conn.cursor()
    check_db_tables()

    registerSelf()
    # Deregister self if service is shut down
    signal.signal(signal.SIGINT, signalHandler)
    signal.signal(signal.SIGTERM, signalHandler)
    atexit.register(deregisterSelf)

    serve()

    cursor.close()
    conn.close()