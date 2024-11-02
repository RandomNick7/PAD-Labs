const express = require('express');
const http = require("http");
const WebSocket = require("ws");
const axios = require('axios');
const jwt = require('jsonwebtoken');
const opossum = require('opossum');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');


let PORT = 6969;
let services = {};
let clients = {};
let user_port = 9000;
let game_port = 7000;
let websocket_port = 7500;
let service_discovery_url = process.env.SERVICE_DISCOVERY_URL;

let ping_count = 0;
let timestamp = Date.now();

const timeout_max = 5000; //ms
const ping_limit = 5;

const app = express();
app.use(express.json());
const server = http.createServer(app);
const wss = new WebSocket.Server({server})

const USER_PROTO_PATH = __dirname + '/protos/user_routes.proto';
const GAME_PROTO_PATH = __dirname + '/protos/game_routes.proto';
const loaderOptions = {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
};

const userPackageDef = protoLoader.loadSync(USER_PROTO_PATH, loaderOptions);
const userRouter = grpc.loadPackageDefinition(userPackageDef).user_routes;

const gamePackageDef = protoLoader.loadSync(GAME_PROTO_PATH, loaderOptions);
const gameRouter = grpc.loadPackageDefinition(gamePackageDef).game_routes;



function createClient(name, id){
  if (name.startsWith("user")){
    let address = `${id}:${user_port}`
    return new userRouter.UserRoutes(address, grpc.credentials.createInsecure());
  }else if (name.startsWith("game")){
    let address = `${id}:${game_port}`
    return new gameRouter.GameRoutes(address, grpc.credentials.createInsecure());
  }
}


function createCircuitBreaker(name){
  /**
   * Returns a circuit breaker with predefined options
   * 
   * The options are defined within the function
   * The circuit breaker removes the corresponding service from discovery if it opens
   */
  const options = {
    name: name,
    errorThresholdPercentage: 25,
    timeout: timeout_max,
    rollingCountTimeout: timeout_max * 3.5, // Count the errors every few seconds instead
    resetTimeout: 10000,                    // Try again after 10s
    errorFilter: (err) => {
      if (err.status >= 500 || err.status == 408){
        return true
      }else{
        return false
      }
    }
  }

  let circuitBreaker = new opossum(gRPCAsyncWrapper, options)
  circuitBreaker.on("open", async () => {
    console.log("Opened breaker!")
    try{
      await axios.post(`${service_discovery_url}/deregister`, {"name": circuitBreaker.options.name});
    }catch(err){
      console.log("Error deregistering service! ", err.message);
    }
  })

  return circuitBreaker
}


async function gRPCAsyncWrapper(client, method, req){
  /**
   * Async wrapper for user client gRPC calls
   * 
   * Used for making the gateway actually wait for the Service to be done
   * Separated from the other wrapper to trip separate circuit breakers
   */
  return new Promise((resolve, reject) => {
    deadline = new Date(Date.now() + timeout_max)
    client[method](req.body, {deadline: deadline}, (err, response) => {
      if(err){
        if (err.code == grpc.status.DEADLINE_EXCEEDED){
          reject({status: 408, err:"Request Timeout"})
        }else{
          reject(err)
        }
      }else{
        resolve(response)
      }
    })
  })
}


async function setUpClients(){
  /**
   * Generates a list of clients and breakers for each, according to discovery
   * 
   * Makes sure the client list corresponds with the service list
   */
  try{
    services = await axios.get(`${service_discovery_url}/services`);
    services = services.data;
    
    for(let key in services){
      if(!(key in clients)){
        let gRPCClient = createClient(key, services[key])
        clients[key] = [createCircuitBreaker(key), gRPCClient, 0];
      }
    }

    for(let key in clients){
      if(!(key in services)){
        delete clients[key];
      }
    }
  }catch{
    console.log("Failed to sync gRPC clients with services!")
  }
}


function pickService(name){
  /**
   * Function that returns the client with a desired name, with the fewest requests
   */
  let target_task = null
  let min_task_count = Infinity
  for(let key in clients){
    if(key.startsWith(name) && clients[key][2] < min_task_count && clients[key][0].closed){
      target_task = key
      min_task_count = clients[key][2]
    }
  }

  if(target_task != null){
    return clients[target_task]
  }else{
    return null
  }
}


async function registerSelf(){
  try{
    await axios.post(`${service_discovery_url}/register`, {Gateway: process.env.HOSTNAME});
  }catch(err){
    console.log("Error registering gateway! ", err.message);
  }
}


async function RPC(req, res, service_name, method){
  /**
   * General-purpose function used for making calls to specific services
   */
  let service = pickService(service_name)

  if(service != null){
    service[2] += 1
    try{
      response = await service[0].fire(service[1], method, req)
      res.status(response["status"]).json({body: response})
    }catch(error){
      if(error.code == "ETIMEDOUT"){
        res.status(408).json({error: "Request Timed Out!"})
      }else if(error.code =="EOPENBREAKER"){
        res.status(503).json({error: "Service temporarily unavailable. Try again later"})
      }else{
        res.status(500).json({error: "Internal server error!", log: error})
      }
    }
    service[2] -= 1
  }else{
    res.status(503).json({error: "Service temporarily unavailable. Try again later"})
  }
  return res
}


function countPings(req, res, next){
  const current_time = Date.now()
  const time_window = 5000

  // Every X seconds, clear the count
  if(current_time - timestamp > time_window){
    if(ping_count > ping_limit){
      console.log(`CAUTION: High number of requests! ${ping_count} over the last ${time_window/1000} seconds`)
    }
    ping_count = 0
    timestamp = current_time
  }

  // Make sure to count the ping that triggered this function too
  ping_count++

  // If a hard limit is needed:
  // if(ping_count > ping_limit){
  //   return res.status(429).send("Too Many Requests");
  // }
  next();
}

function authenticate(req, res, next){
  let auth = req.headers["authorization"]
  let token = auth && auth.split(' ')[1]

  if(token == null){
    return res.status(401).json({error: "Unauthorized"})
  }

  jwt.verify(token, process.env.JWT_SECRET, (err, data) => {
    if(err || !data.id || !data.user){
      return res.status(403).json({error:"Forbidden"})
    }
    
    req.body["srcID"] = data.id
    next()
  })
}


wss.on('connection', (ws) => {
  let service = pickService("game-service")
  if(service == null){
    ws.send("Service currently unavailable");
    ws.close();
    return;
  }

  service[2] += 1;
  let serviceURL = `ws://${services[service[0].options.name]}:${websocket_port}`;

  const serviceSocket = new WebSocket(serviceURL);

  ws.on('message', (message) => {
    serviceSocket.send(message);
  });

  serviceSocket.on('message', (message) => {
    ws.send(message);
  });

  ws.on('close', () => {
    serviceSocket.close();
    service[2] -= 1;
  });
})



// ROUTES - USER

app.post('/login', countPings, async (req, res) => {
  RPC(req, res, "user-service", "tryLogin")
})

app.get('/profile', countPings, authenticate, async (req, res) => {
  req.body["userID"] = req.body["srcID"]
  RPC(req, res, "user-service", "checkProfile")
})

app.get('/profile/:userID', countPings, authenticate, async (req, res) => {
  req.body["userID"] = req.params.userID
  RPC(req, res, "user-service", "checkProfile")
})

app.post('/frequest/:userID', countPings, authenticate, async (req, res) => {
  req.body["destID"] = req.params.userID
  RPC(req, res, "user-service", "sendFriendRequest")
})


// ROUTES - GAME

app.get('/lobby', countPings, authenticate, async (req, res) => {
  RPC(req, res, "game-service", "getLobbies")
})

app.get('/lobby/:lobbyID', countPings, authenticate, async (req, res) => {
  req.body["lobbyID"] = req.params.lobbyID
  RPC(req, res, "game-service", "getLobby")
})

app.post('/lobby/make', countPings, authenticate, async (req, res) => {
  req.body["userID"] = req.body["srcID"]
  RPC(req, res, "game-service", "makeLobby")
})

app.post('/lobby/:lobbyID/join', countPings, authenticate, async (req, res) => {
  req.body["lobbyID"] = req.params.lobbyID
  req.body["userID"] = req.body["srcID"]
  RPC(req, res, "game-service", "joinLobby")
})

app.get('/lobby/:lobbyID/leave', countPings, authenticate, async (req, res) => {
  req.body["lobbyID"] = req.params.lobbyID
  req.body["userID"] = req.body["srcID"]
  RPC(req, res, "game-service", "leaveLobby")
})

app.get('/game/:gameID', countPings, authenticate, async (req, res) => {
  req.body["gameID"] = req.params.gameID
  RPC(req, res, "game-service", "getGame")
})


// ROUTES - MISC.

app.get('/status', (req, res) => {
  res.status(200).json({"status": "online"})
})


server.listen(PORT, async () => {
  console.log(`App listening on port ${PORT}`)
  await registerSelf();
  //await cacheClient.connect()

  // Make the gateway check Service Discovery every 3 seconds
  setInterval(setUpClients, 3000);
})