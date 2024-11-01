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

import user_routes_pb2 as pb2
import user_routes_pb2_grpc as pb2_grpc
import health_pb2 as hpb2
import health_pb2_grpc as hpb2_grpc


def registerSelf():
    response = requests.post(f"{SERVICE_DISCOVERY_URL}/register", json = {f"user-service": INSTANCE_ID})

    if response.status_code == 201:
        logger.info("Registered a User Service!")
    else:
        logger.info("Error registering service!")


def deregisterSelf():
    response = requests.post(f"{SERVICE_DISCOVERY_URL}/deregister", json = {f"user-service": INSTANCE_ID})

    if response.status_code == 200:
        logger.info("Removed a User Service!")
    else:
        logger.info("Error deregistering service!")


def signalHandler(signal, frame):
    deregisterSelf()
    exit(0)


def generate_token(target_user):
    """Generates a JWT token given a user"""
    secret_key = os.getenv('JWT_SECRET')
    payload = {
        "id": target_user[0],
        "user": target_user[1]
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
        
        query = "SELECT username, password FROM user_info WHERE username=%s"
        cursor.execute(query, (request.username,))
        target_user = cursor.fetchone()

        if request.newAccount:
            if target_user is None:
                query = "INSERT INTO user_info (username, password) VALUES (%s, %s) RETURNING id"
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

        sleep(4.5)
        
        return pb2.LoginConfirm(**result)
    
    def checkProfile(self, request, context):
        query = "SELECT username FROM user_info WHERE id=%s"
        cursor.execute(query, (request.userID,))
        target_user = cursor.fetchone()

        if target_user:
            result = {"status": 200, "username": target_user[0]}
        else:
            result = {"status": 404}

        return pb2.UserInfo(**result)

    def sendFriendRequest(self, request, context):
        if request.srcID != request.destID:
            query = "SELECT friends FROM user_info WHERE id=%s"
            cursor.execute(query, (request.destID,))
            target_user = cursor.fetchone()

            if target_user:
                if request.srcID not in target_user[0]:
                    query = "UPDATE user_info \
                        SET friends = array_append(friends, %s) \
                        WHERE id = %s"
                    cursor.execute(query, (request.srcID, request.destID))
                    result = {"status": 200}
                else:
                    result = {"status": 400}
            else:
                result = {"status": 404}
        else:
            result = {"status": 400}

        return pb2.Status(**result)


def addAllServicers(server):
    pb2_grpc.add_UserRoutesServicer_to_server(UserService(), server)
    hpb2_grpc.add_HealthServicer_to_server(HealthService(), server)


def check_db_tables():
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'user_data'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE user_data")

    cursor.execute("CREATE TABLE IF NOT EXISTS user_info\
        (id SERIAL PRIMARY KEY, username TEXT, password TEXT, friends INTEGER[])")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers = 1))
    addAllServicers(server)

    server.add_insecure_port("[::]:9000")
    server.start()

    logger.info("Server up and running!")
    server.wait_for_termination()


if __name__ == '__main__':
    INSTANCE_ID = os.environ.get("HOSTNAME")
    SERVICE_DISCOVERY_URL = os.environ.get("SERVICE_DISCOVERY_URL")
    
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