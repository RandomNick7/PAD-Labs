import grpc
from concurrent import futures

import user_routes_pb2 as pb2
import user_routes_pb2_grpc as pb2_grpc

class UserService(pb2_grpc.UserRoutesServicer):
    def tryLogin(self, request, context):
        print("Message received!")
        if request.newAccount:
            result = request.username + ' ' + request.password
        else:
            result = request.password + ' ' + request.username
        result = {"status": 200, "token": result}

        return pb2.LoginConfirm(**result)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
    pb2_grpc.add_UserRoutesServicer_to_server(UserService(), server)
    server.add_insecure_port("[::]:9000")
    print("Server up and running!")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()