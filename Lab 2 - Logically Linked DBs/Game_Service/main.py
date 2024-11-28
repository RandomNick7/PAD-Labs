import os
import grpc
import random
import requests
import logging
import signal
import atexit
import asyncio
import psycopg2
import websockets
from time import sleep
from concurrent import futures
from prometheus_client import start_http_server, Counter

import game_routes_pb2 as pb2
import game_routes_pb2_grpc as pb2_grpc
import health_pb2 as hpb2
import health_pb2_grpc as hpb2_grpc


request_counter = Counter("game_service_total_requests", "Total requests to the Game Service")

def registerSelf():
    response = requests.post(f"{SERVICE_DISCOVERY_URL}/register", json = {f"game-service": INSTANCE_ID})

    if response.status_code == 201:
        logger.info("Registered a Game Service!")
    else:
        logger.info("Error registering service!")


def deregisterSelf():
    response = requests.post(f"{SERVICE_DISCOVERY_URL}/deregister", json = {f"game-service": INSTANCE_ID})

    if response.status_code == 200:
        logger.info("Removed a Game Service!")
    else:
        logger.info("Error deregistering service!")


def signalHandler(signal, frame):
    deregisterSelf()
    exit(0)


class HealthService(hpb2_grpc.HealthServicer):
    def Check(self, request, context):
        return hpb2.HealthCheckResponse(status = hpb2.HealthCheckResponse.SERVING)


class GameService(pb2_grpc.GameRoutesServicer):
    def getLobbies(self, request, context):
        """Returns a list of available lobbies from the database"""
        query = "SELECT name, curr_members, max_members FROM lobby_tbl WHERE status!=0"
        cursor.execute(query)

        request_counter.inc()

        lobby_list = cursor.fetchall()
        proto_lobbies = []
        for lobby in lobby_list:
            p_lobby = pb2.LobbyInfo()
            p_lobby.name = lobby[0]
            p_lobby.currMembers = len(lobby[1])
            p_lobby.maxMembers = lobby[2]
            proto_lobbies.append(p_lobby)

        result = {"status": 200, "lobbies": proto_lobbies}
        return pb2.LobbyList(**result)
    
    def getLobby(self, request, context):
        query = "SELECT name, curr_members, max_members FROM lobby_tbl WHERE status!=0 AND id=%s"
        cursor.execute(query, (request.lobbyID,))
        
        request_counter.inc()
        lobby = cursor.fetchone()
        if lobby:
            result = {
                "status": 200, 
                "name": lobby[0],
                "currMembers": len(lobby[1]),
                "maxMembers": lobby[2],
                "players": lobby[1]
            }
        else:
            result = {"status": 404}

        return pb2.LobbyDetails(**result)
    
    def makeLobby(self, request, context):
        query = "INSERT INTO lobby_tbl (name, curr_members, max_members, status) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (request.name, [request.userID], request.maxCount, 1))
        request_counter.inc()
        result = {
            "status": 200,
            "currMembers": 1,
            "maxMembers": request.maxCount,
            "name": request.name,
            "players": [request.userID]
        }
        return pb2.LobbyDetails(**result)
    
    def joinLobby(self, request, context):
        query = "SELECT curr_members, max_members FROM lobby_tbl WHERE status!=0 AND id=%s"
        cursor.execute(query, (request.lobbyID,))
        request_counter.inc()

        lobby = cursor.fetchone()
        if lobby:
            if len(lobby[0]) + 1 < lobby[1]:
                query = "UPDATE lobby_tbl \
                    SET curr_members = array_append(curr_members, %s) \
                    WHERE id = %s"
                cursor.execute(query, (request.userID, request.lobbyID))
                result = {"status": 200}
            else:
                result = {"status": 400}
        else:
            result = {"status": 404}

        return pb2.LobbyDetails(**result)
    
    def leaveLobby(self, request, context):
        query = "SELECT curr_members, max_members FROM lobby_tbl WHERE status!=0 AND id=%s"
        cursor.execute(query, (request.lobbyID,))
        request_counter.inc()

        lobby = cursor.fetchone()
        if lobby:
            query = "UPDATE lobby_tbl \
                SET curr_members = array_remove(curr_members, %s) \
                WHERE id = %s \
                RETURNING curr_members"
            cursor.execute(query, (request.userID, request.lobbyID))
            members = cursor.fetchone()[0]
            if len(members) == 0:
                query = "DELETE FROM lobby_tbl WHERE id = %s;"
                cursor.execute(query, (request.lobbyID,))

            result = {"status": 200}
        else:
            result = {"status": 404}

        return pb2.Status(**result)

    def getGame(self, request, context):
        result = {"status": 200}
        # Placeholder...
        return pb2.Status(**result)
    
    def endGame(self, request, context):
        # Made-up data for testing purposes
        players = []
        for i in range(random.randint(5, 20)):
            player_info = pb2.PlayerData()

            provinces = []
            for i in range(random.randint(10, 50)):
                provinces.append(random.randint(1, 400))
            
            player_info.population = random.randint(10000, 250000)
            player_info.provinceIDs.extend(provinces)
            players.append(player_info)
        
        query = "UPDATE lobby_tbl SET status = -1 WHERE id = %s RETURNING status"
        cursor.execute(query, (request.gameID,))
        lobby = cursor.fetchone()

        if lobby != None:
            result = {"status": 200, "nations": players}
        else:
            result = {"status": 404}
        return pb2.MapData(**result)

    def continueGame(self, request, context):
        query = "UPDATE lobby_tbl SET status = 1 WHERE id = %s RETURNING status"
        cursor.execute(query, (request.gameID,))
        lobby = cursor.fetchone()

        if lobby != None:
            result = {"status": 200}
        else:
            result = {"status": 404}
        return pb2.Status(**result)

    def closeGame(self, request, context):
        query = "DELETE FROM lobby_tbl WHERE id = %s;"
        cursor.execute(query, (request.gameID,))
        
        result = {"status": 200}
        return pb2.Status(**result)




def addAllServicers(server):
    pb2_grpc.add_GameRoutesServicer_to_server(GameService(), server)
    hpb2_grpc.add_HealthServicer_to_server(HealthService(), server)

    
def check_db_tables():
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'game_data'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE game_data")

    cursor.execute("CREATE TABLE IF NOT EXISTS lobby_tbl\
        (id SERIAL PRIMARY KEY, name TEXT, curr_members INTEGER[], max_members SMALLINT, status SMALLINT)")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
    addAllServicers(server)

    server.add_insecure_port("[::]:7000")
    server.start()

    logger.info("Server up and running!")
    return server


async def process_websocket(websocket):
    async for message in websocket:
        logger.info(message)
        await websocket.send(f"Echo: {message}")


async def websock():
    async with websockets.serve(process_websocket, "0.0.0.0", 7500):
        await asyncio.Future()


if __name__ == '__main__':
    INSTANCE_ID = os.environ.get("HOSTNAME")
    SERVICE_DISCOVERY_URL = os.environ.get("SERVICE_DISCOVERY_URL")

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    start_http_server(7700)

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
    asyncio.run(websock())
    grpcServer.wait_for_termination()

    cursor.close()
    conn.close()