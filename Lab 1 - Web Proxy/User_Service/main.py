import grpc
import logging
from time import sleep
from concurrent import futures

import user_routes_pb2 as pb2
import user_routes_pb2_grpc as pb2_grpc

class UserService(pb2_grpc.UserRoutesServicer):
    def tryLogin(self, request, context):
        logger.info("Message received!")
        if request.newAccount:
            result = request.username + ' ' + request.password
        else:
            result = request.password + ' ' + request.username
        result = {"status": 200, "token": result}
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

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    serve()