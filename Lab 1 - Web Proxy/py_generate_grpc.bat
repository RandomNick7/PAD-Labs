@echo off
cd ./User_Service
CALL venv/Scripts/activate.bat
python -m grpc_tools.protoc -I=../Gateway/protos --python_out=. --grpc_python_out=. ../Gateway/protos/user_routes.proto
python -m grpc_tools.protoc -I=../Gateway/protos --python_out=. --grpc_python_out=. ../Gateway/protos/health.proto
cd ../Game_Service
python -m grpc_tools.protoc -I=../Gateway/protos --python_out=. --grpc_python_out=. ../Gateway/protos/game_routes.proto
python -m grpc_tools.protoc -I=../Gateway/protos --python_out=. --grpc_python_out=. ../Gateway/protos/health.proto
CALL deactivate