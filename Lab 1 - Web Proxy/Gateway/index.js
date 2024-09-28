const express = require('express');
const axios = require('axios');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const port = 6969
const target_addr = "user-service"
const target_port = 9000
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
const client = new userRouter.UserRoutes(`${target_addr}:${target_port}`, grpc.credentials.createInsecure())


app.post('/login', async (req, res) => {
  try{
    console.log("Message sent!")
    client.tryLogin(req.body, function(err, response){
      res.json({"data": response})
    })
  }catch(error){
    res.status(500).json({error: "Internal server error!"})
  }
})

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`)
})