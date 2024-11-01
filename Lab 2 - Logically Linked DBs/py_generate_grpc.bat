@echo off
CALL gRPC/Scripts/activate.bat
python -m grpc_tools.protoc -I=./Gateway/protos --python_out=./User_Service --grpc_python_out=./User_Service ./Gateway/protos/user_routes.proto
python -m grpc_tools.protoc -I=./Gateway/protos --python_out=./User_Service --grpc_python_out=./User_Service ./Gateway/protos/health.proto
python -m grpc_tools.protoc -I=./Gateway/protos --python_out=./Game_Service --grpc_python_out=./Game_Service ./Gateway/protos/game_routes.proto
python -m grpc_tools.protoc -I=./Gateway/protos --python_out=./Game_Service --grpc_python_out=./Game_Service ./Gateway/protos/health.proto
CALL deactivate