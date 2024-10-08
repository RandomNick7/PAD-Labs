import os
import grpc
import logging
import psycopg2
import jwt
from time import sleep
from concurrent import futures

import game_routes_pb2 as pb2
import game_routes_pb2_grpc as pb2_grpc
import health_pb2 as hpb2
import health_pb2_grpc as hpb2_grpc



class HealthService(hpb2_grpc.HealthServicer):
    def Check(self, request, context):
        return hpb2.HealthCheckResponse(status = hpb2.HealthCheckResponse.SERVING)


class GameService(pb2_grpc.GameRoutesServicer):
    def getLobbies(self, request, context):
        """Returns a list of available lobbies from the database"""
        result = {}
        
        query = "SELECT name, curr_members, max_members FROM lobby_tbl WHERE status!=0"
        cursor.execute(query)

        lobby_list = cursor.fetchall()
        proto_lobbies = []
        for lobby in lobby_list:
            p_lobby = pb2.LobbyInfo()
            p_lobby.name = lobby[0]
            p_lobby.currMembers = lobby[1]
            p_lobby.maxMembers = lobby[2]
            proto_lobbies.append(p_lobby)

        return pb2.LobbyList(lobbies = proto_lobbies)


def addAllServicers(server):
    pb2_grpc.add_GameRoutesServicer_to_server(GameService(), server)
    hpb2_grpc.add_HealthServicer_to_server(HealthService(), server)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
    addAllServicers(server)

    server.add_insecure_port("[::]:7000")
    server.start()

    logger.info("Server up and running!")
    server.wait_for_termination()


def check_db_tables():
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'game_data'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE game_data")

    cursor.execute("CREATE TABLE IF NOT EXISTS lobby_tbl\
        (id SERIAL PRIMARY KEY, name TEXT, curr_members SMALLINT, max_members SMALLINT, status SMALLINT)")


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