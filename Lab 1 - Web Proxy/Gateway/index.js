const express = require('express');
const redis = require('redis');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const self_port = 6969
const user_addr = "user-service"
const user_port = 9000
const game_addr = "game-service"
const game_port = 7000

const timeout_max = 10000 //ms
const ping_limit = 5

let timestamp = Date.now()
let ping_count = 0

const app = express()
app.use(express.json())

const USER_PROTO_PATH = __dirname + '/protos/user_routes.proto';
const GAME_PROTO_PATH = __dirname + '/protos/game_routes.proto';
const loaderOptions = {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
}

const userPackageDef = protoLoader.loadSync(USER_PROTO_PATH, loaderOptions);
const userRouter = grpc.loadPackageDefinition(userPackageDef).user_routes;
const userClient = new userRouter.UserRoutes(`${user_addr}:${user_port}`, grpc.credentials.createInsecure())

const gamePackageDef = protoLoader.loadSync(GAME_PROTO_PATH, loaderOptions);
const gameRouter = grpc.loadPackageDefinition(gamePackageDef).game_routes;
const gameClient = new gameRouter.GameRoutes(`${game_addr}:${game_port}`, grpc.credentials.createInsecure())

const cacheClient = redis.createClient({url: "redis://redis:6379"})
let cacheConnected = false


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


async function asyncWrapper(client, method, req){
  /**
   * Async wrapper for all gRPC calls
   * 
   * Used for making the gateway actually wait for the Service to be done
   * NOTE: Promise is always fulfilled, "reject" is redundant right now
   */
  return new Promise((resolve, reject) => {
    deadline = new Date(Date.now() + timeout_max)
    client[method](req.body, {deadline: deadline}, (err, response) => {
      if(err){
        if (err.code == grpc.status.DEADLINE_EXCEEDED){
          resolve({status: 408, err:"Request Timeout"})
        }else{
          resolve(err)
        }
      }else{
        resolve(response)
      }
    })
  })
}


// VVV   ROUTES   VVV

app.post('/login', countPings, async (req, res) => {
  try{
    response = await asyncWrapper(userClient, "tryLogin", req)
    res.status(response["status"]).json({"data": response})
  }catch(error){
    if(response["status"] == 408){
      res.status(408).json({"data": response})
    }else{
      res.status(500).json({error: "Internal server error! " + error})
    }
  }
})


app.get('/lobby', countPings, async(req, res) => {
  try{
    if(!cacheConnected){
      await cacheClient.connect()
      cacheConnected = true
    }

    // response = JSON.parse(await cacheClient.get("lobbies"))
    response = null
    if(!response){
      response = await asyncWrapper(gameClient, "getLobbies", req)
      await cacheClient.set("lobbies", JSON.stringify(response))
    }

    res.status(200).json({"data": response})
  }catch(error){
    console.log(error)
    if(response["status"] == 408){
      res.status(408).json({"data": response})
    }else{
      res.status(500).json({error: "Internal server error! " + error})
    }
  }
})


app.get('/status', (req, res) => {
  res.status(200).json({"status": "online"})
})


app.listen(self_port, () => {
  console.log(`App listening on port ${self_port}`)
})