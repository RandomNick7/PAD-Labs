import os
import grpc
import logging
import psycopg2
import jwt
from time import sleep
from concurrent import futures

import user_routes_pb2 as pb2
import user_routes_pb2_grpc as pb2_grpc


def generate_token(target_user):
    secret_key = os.getenv('JWT_SECRET')
    payload = {
        "user_id": target_user[0],
        "username": target_user[1]
    }
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token


class UserService(pb2_grpc.UserRoutesServicer):
    def tryLogin(self, request, context):
        logger.info("Message received!")
        result = {}
        
        query = "SELECT * FROM user_credentials WHERE username=%s"
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
                # User Not Found!
                result = {"status": 404}

        sleep(9)
        logger.info("Message replied!")

        return pb2.LoginConfirm(**result)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers = 1))
    pb2_grpc.add_UserRoutesServicer_to_server(UserService(), server)
    server.add_insecure_port("[::]:9000")
    logger.info("Server up and running!")
    server.start()
    server.wait_for_termination()


def check_db_tables():
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'user_data'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE user_data")

    cursor.execute("CREATE TABLE IF NOT EXISTS user_credentials\
        (id SERIAL PRIMARY KEY, username TEXT, password TEXT)")


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    conn.autocommit = True
    cursor = conn.cursor()
    check_db_tables()

    serve()

    cursor.close()
    conn.close()