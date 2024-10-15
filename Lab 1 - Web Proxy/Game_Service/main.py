import os
import grpc
import requests
import logging
import signal
import atexit
import psycopg2
import jwt
import asyncio
import websockets
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


def registerSelf():
    service_definition = {
        "ID": INSTANCE_ID,
        "Name": f"game-service-{INSTANCE_ID}"
    }

    response = requests.put(f"{consul_url}/v1/agent/service/register", json=service_definition)

    if response.status_code == 200:
        logger.info("Registered a Game Service successfully!")
    else:
        logger.info("Error registering service!")


def deregisterSelf():
    requests.put(f"{consul_url}/v1/agent/service/deregister/{INSTANCE_ID}")


def addAllServicers(server):
    pb2_grpc.add_GameRoutesServicer_to_server(GameService(), server)
    hpb2_grpc.add_HealthServicer_to_server(HealthService(), server)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
    addAllServicers(server)

    server.add_insecure_port("[::]:7000")
    server.start()

    logger.info("Server up and running!")
    return server


def check_db_tables():
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'game_data'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE game_data")

    cursor.execute("CREATE TABLE IF NOT EXISTS lobby_tbl\
        (id SERIAL PRIMARY KEY, name TEXT, curr_members SMALLINT, max_members SMALLINT, status SMALLINT)")


def signalHandler(signal, frame):
    deregisterSelf()
    logger.info("Deregistered a Game Service")
    exit(0)


async def process_websocket(websocket):
    async for message in websocket:
        logger.info(message)
        await websocket.send(f"Echo: {message}")

async def main():
    async with websockets.serve(process_websocket, "0.0.0.0", 7500):
        await asyncio.Future()


if __name__ == '__main__':
    consul_url = "http://consul:8500"
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

    grpcServer = serve()
    asyncio.run(main())
    grpcServer.wait_for_termination()

    cursor.close()
    conn.close()