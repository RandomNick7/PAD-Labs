import asyncio
import grpc
from concurrent import futures

import user_routes_pb2 as pb2
import user_routes_pb2_grpc as pb2_grpc

port = 9000

class UserService(pb2_grpc.UserRoutesServicer):
    async def tryLogin(self, request, context):
        if request.newAccount:
            result = request.username + ' ' + request.password
        else:
            result = request.password + ' ' + request.username
        result = {"status": 200, "token": result}

        return pb2.LoginConfirm(**result)

async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers = 10))
    pb2_grpc.add_UserRoutesServicer_to_server(UserService(), server)
    server.add_insecure_port("[::]:" + str(port))
    await server.start()
    print("Server up and running!")
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())