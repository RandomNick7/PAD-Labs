const express = require('express');
const axios = require('axios');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const self_port = 6969
const user_addr = "user-service"
const user_port = 9000
const timeout_max = 10000 //ms
let timed_out = false

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
const client = new userRouter.UserRoutes(`${user_addr}:${user_port}`, grpc.credentials.createInsecure())


async function asyncWrapper(method, req){
  return new Promise((resolve, reject) => {
    deadline = new Date(Date.now() + timeout_max)
    client[method](req.body, {deadline: deadline}, (err, response) => {
      if(err){
        if (err.code == grpc.status.DEADLINE_EXCEEDED){
          timed_out = true
          return reject("Request Timeout")
        }
        return reject(err)
      }
      resolve(response)
    })
  })
}


app.post('/login', async (req, res) => {
  try{
    console.log("Message sent!")
    timed_out = false
    response = await asyncWrapper("tryLogin", req)
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