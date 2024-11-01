const express = require('express');

const app = express();

let PORT = 4444
let services = {}

app.use(express.json());

function addEntry(entry){
  let count = 1
  let key = Object.keys(entry)[0]

  let newKey = key + count.toString()
  while(services.hasOwnProperty(newKey)){
    count += 1
    newKey = key + count.toString()
  }

  services[newKey] = entry[key];
}

app.post('/register', (req, res) => {
  addEntry(req.body)
  res.status(201).json()
})


app.post('/deregister', (req, res) => {
  delete services[req.body.name]
  res.status(200).json({"response": 200})
})


app.get('/services', (req, res) => {
  res.status(200).json(services)
})


app.get('/status', (req, res) => {
  res.status(200).json({"status": "online"})
})


app.listen(PORT, () => {
  console.log(`App listening on port ${PORT}`)
})