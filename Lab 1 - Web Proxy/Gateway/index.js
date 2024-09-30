const express = require('express');
const axios = require('axios');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const self_port = 6969
const user_addr = "user-service"
const user_port = 9000
const timeout_max = 10000 //ms
const ping_limit = 5

let timed_out = false
let timestamp = Date.now()
let ping_count = 0

const app = express()
app.use(express.json())

const PROTO_PATH = __dirname + '/protos/user_routes.proto';
const loaderOptions = {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
}

const packageDef = protoLoader.loadSync(PROTO_PATH, loaderOptions);
const userRouter = grpc.loadPackageDefinition(packageDef).user_routes;
const user_client = new userRouter.UserRoutes(`${user_addr}:${user_port}`, grpc.credentials.createInsecure())

function countPings(req, res, next){
  const current_time = Date.now()
  const time_window = 5000

  // Every X seconds, clear the count
  if(current_time - timestamp > time_window){
    ping_count = 0
    timestamp = current_time
  }

  // Make sure to count the ping that triggered this function too
  ping_count++

  // If limit is exceeded, write something somewhere
  if(ping_count > ping_limit){
    console.log(`CAUTION: High number of requests! ${ping_count} over the last ${time_window/1000} seconds`)
    // If a hard limit is needed -> return res.status(429).send("Too Many Requests");
  }
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
          timed_out = true
          resolve("Request Timeout")
        }
        resolve(err)
      }else{
        resolve(response)
      }
    })
  })
}


app.post('/login', countPings, async (req, res) => {
  try{
    console.log("Message sent!")
    timed_out = false
    response = await asyncWrapper(user_client, "tryLogin", req)
    res.status(response["status"]).json({"data": response})
  }catch(error){
    if(timed_out){
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