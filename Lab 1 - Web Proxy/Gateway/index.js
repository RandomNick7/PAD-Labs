const express = require('express');
const axios = require('axios');
const opossum = require('opossum');
const Consul = require('consul');
const redis = require('redis');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const self_port = 6969;
const NGINX_URL = "nginx:80"
const consul_addr = "consul";
const consul_port = 8500;
let consul_url = `http://${consul_addr}:${consul_port}`

const timeout_max = 3000; //ms
const ping_limit = 5;

let ping_count = 0;
let timestamp = Date.now();
let user_services = [];
let game_services = [];

const app = express();
const consul = new Consul({
  host: consul_addr,
  port: consul_port
});

app.use(express.json());

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
const userClient = new userRouter.UserRoutes(`${NGINX_URL}`, grpc.credentials.createInsecure());

const gamePackageDef = protoLoader.loadSync(GAME_PROTO_PATH, loaderOptions);
const gameRouter = grpc.loadPackageDefinition(gamePackageDef).game_routes;
const gameClient = new gameRouter.GameRoutes(`${NGINX_URL}`, grpc.credentials.createInsecure());

const cacheClient = redis.createClient({url: "redis://redis:6379"});
let cacheConnected = false;

const userCircuitBreaker = new opossum(userAsyncWrapper, {
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
})


const gameCircuitBreaker = new opossum(gameAsyncWrapper, {
  errorThresholdPercentage: 25,
  rollingCountTimeout: timeout_max * 3.5, // Count the errors every few seconds instead
  resetTimeout: 10000,                    // Try again after 10s
  errorFilter: (err) => {
    if (err.status >= 500 || err.status == 408){
      return true
    }else{
      return false
    }
  }
})


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


async function userAsyncWrapper(method, req){
  /**
   * Async wrapper for user client gRPC calls
   * 
   * Used for making the gateway actually wait for the Service to be done
   * Separated from the other wrapper to trip separate circuit breakers
   * NOTE: Promise is always fulfilled, "reject" is redundant right now
   */
  return new Promise((resolve, reject) => {
    deadline = new Date(Date.now() + timeout_max)
    userClient[method](req.body, {deadline: deadline}, (err, response) => {
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


async function gameAsyncWrapper(method, req){
  /**
   * Async wrapper for all gRPC calls
   * 
   * Used for making the gateway actually wait for the Service to be done
   * NOTE: Promise is always fulfilled, "reject" is redundant right now
   */
  return new Promise((resolve, reject) => {
    deadline = new Date(Date.now() + timeout_max)
    gameClient[method](req.body, {deadline: deadline}, (err, response) => {
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


async function registerSelf(){
  let serviceDefinition = {
    "ID": "Gateway",
    "Name": "Gateway",
    "Address": "localhost",
    "Port": self_port,
    "Tags": ['nodejs']
  };

  try{
    await axios.put(`${consul_url}/v1/agent/service/register`, serviceDefinition);
  }catch(err){
    console.log("Error registering service! ", err.message);
  }
}


process.on("SIGINT", async() => {
  try{
    // Deregister all known services
  for(let service of user_services){
    await axios.put(`${consul_url}/v1/agent/service/deregister/${service}`)
  }
  for(let service of game_services){
    await axios.put(`${consul_url}/v1/agent/service/deregister/${service}`)
  }
    // Deregister self afterwards
    await axios.put(`${consul_url}/v1/agent/service/deregister/Gateway`);
  }catch(err){
    console.log("Error deregistering service! ", err.message);
  }finally{
    process.exit();
  }
})


userCircuitBreaker.on("open", async () => {
  console.log("Opened breaker!")
  for(let service of user_services){
    let id = service.slice(service.lastIndexOf("-") + 1)
    await axios.put(`${consul_url}/v1/agent/service/deregister/${id}`)
  }
})


userCircuitBreaker.on("close", async () => {
  console.log("Closed breaker!")
  // Normally, the containers would have restarted and the services would have re-registered
  // Since the containers don't crash nor restart, we'll pretend they've restarted anyway
  for(let service of user_services){
    let id = service.slice(service.lastIndexOf("-") + 1)
    let serviceDefinition = {
      "ID": id,
      "Name": service
    };
    await axios.put(`${consul_url}/v1/agent/service/register`, serviceDefinition);
  }
})


gameCircuitBreaker.on("open", async () => {
  console.log("Opened breaker!")
  for(let service of game_services){
    let id = service.slice(service.lastIndexOf("-") + 1)
    await axios.put(`${consul_url}/v1/agent/service/deregister/${id}`)
  }
})


gameCircuitBreaker.on("close", async () => {
  console.log("Closed breaker!")
  // Normally, the containers would have restarted and the services would have re-registered
  // Since the containers don't crash nor restart, we'll pretend they've restarted anyway
  for(let service of game_services){
    let id = service.slice(service.lastIndexOf("-") + 1)
    let serviceDefinition = {
      "ID": id,
      "Name": service
    };
    await axios.put(`${consul_url}/v1/agent/service/register`, serviceDefinition);
  }
})


// Refresh list of services every 5s from Consul
setInterval(async () => {
  try{
    let services = await axios.get(`${consul_url}/v1/catalog/services`);
    let service_list = Object.keys(services.data)
    if(userCircuitBreaker.closed){
      user_services = service_list.filter((s) => s.startsWith("user"))
    }
    if(gameCircuitBreaker.closed){
      game_services = service_list.filter((s) => s.startsWith("game"))
    }
  }catch{}
}, 5000);


// VVV   ROUTES   VVV

app.post('/login', countPings, async (req, res) => {
  if(userCircuitBreaker.opened){
    return res.status(503).json({error: "Service temporarily unavailable. Try again later"})
  }

  try{
    response = await userCircuitBreaker.fire("tryLogin", req)
    res.status(response["status"]).json({"data": response})
  }catch(error){
    if(error.code == "ETIMEDOUT"){
      res.status(408).json({error: "Request Timed Out!"})
    }else if(error.code =="EOPENBREAKER"){
      res.status(503).json({error: "Service temporarily unavailable. Try again later"})
    }else{
      res.status(500).json({error: "Internal server error!", log: error})
    }
  }
})


app.get('/lobby', countPings, async(req, res) => {
  try{
    if(!cacheConnected){
      await cacheClient.connect()
      cacheConnected = true
    }

    response = JSON.parse(await cacheClient.get("lobbies"))
    if(!response){
      if(gameCircuitBreaker.opened){
        return res.status(503).json({error: "Service temporarily unavailable. Try again later"})
      }
    
      response = await gameCircuitBreaker.fire("getLobbies", req)
      await cacheClient.set("lobbies", JSON.stringify(response))
    }

    res.status(200).json({"data": response})
  }catch(error){
    if(error.code == "ETIMEDOUT"){
      res.status(408).json({error: "Request Timed Out!"})
    }else if(error.code =="EOPENBREAKER"){
      res.status(503).json({error: "Service temporarily unavailable. Try again later"})
    }else{
      res.status(500).json({error: "Internal server error! " + error.message})
    }
  }
})


app.get('/services', async (req, res) => {
  try{
    let services = await axios.get(`${consul_url}/v1/catalog/services`);
    res.status(200).json(services.data)
  }catch(error){
    res.status(500).json({error: "Internal server error! " + error})
  }
})


app.get('/service-info/:serviceName', async (req, res) => {
  const serviceName = req.params.serviceName;
  try{
    services = await consul.catalog.service.nodes(serviceName)
    
    let serviceInfo = services.map(instance => ({
        id: instance.ID,
        address: instance.Address,
        port: instance.ServicePort,
        tags: instance.ServiceTags,
    }));

    res.status(200).json(serviceInfo);
  }catch (error){
    res.status(500).send(error);
  }
});


app.get('/status', (req, res) => {
  res.status(200).json({"status": "online"})
})


app.get('/ws/nginx', (req, res) => {
  res.redirect("ws://nginx:80/ws");
})

app.get('/ws', (req, res) => {
  res.redirect("ws://localhost:7500");
})


app.listen(self_port, async () => {
  console.log(`App listening on port ${self_port}`)
  await registerSelf();
})