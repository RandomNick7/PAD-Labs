# Grand Strategy Multiplayer Game

## Application Suitability Assessment
### Releveance
Every day, thousands of players engage in multiplayer strategy games. It is a somewhat niche market, due to the complexity and required involvement of the games, which can be overwhelming for new players. A more simplistic game can help gather a larger audience while getting the attention of the existing community engaging with other members of the genre.

### Why use Microservices?
An online multiplayer game would fare much better with a microservice-based architecture, as certain components, such as user management and game logic, are better kept separate. The microservice-based apporach allows for independent operation and scaling of the parts of a system, being more resource efficient compared to a monolithic approach. In addition, maintaining or extending the functionalities of the application can be performed more easily due to the services being separated. If something goes wrong with one of the microservices, the others remain unaffected, avoiding the disruption of the rest of the system.

## Service Boundaries
Services:  
User Service - responsible for the creation and authentication of accounts and storing additional information, such as a list of friends  
Game Service - handles lobby creation, joining & listing, in-game chat and the game logic itself, keeping track of each player's actions and in-game statistics  

![Architectural diagram of the system](./Service_Architecture.svg)

## Tech Stack
API Gateway: NodeJS + Express  
Service Discovery: NodeJS + Consul  
User Service & Game Service: Python + Flask  
Databases: PostgreSQL  
Cache: Redis  

Communication between services will be performed via gRPC (using Protobuf) and HTTP (using JSON), in a synchronous manner  
Asynchronous real-time updates to the game performed by the users (issuing orders, moving units, enstilling policies, etc.) will use Websocket connections instead  

## Data Management Design
The requests will be done to the Gateway, which will redirect them accordingly:  

### User Service endpoints:  
`POST /register` - Register a new user using username and password  
```json
{
    "username": "Username",
    "password": "passHash"
}
```
Responses: **201** Created, **409** Conflict (User already exists)

`POST /login` - Log in using existing user credentials
```json
{
    "username": "Username",
    "password": "passHash"
}
```
Responses: **200** OK, **401** Unauthorized (Wrong credentials)

`GET /logout` - Log out of account  
Responses: **200** OK, **401** Unauthorized (Trying to log out without being logged in)

`GET /profile/<UID>` - Get information about a particular user's account, including your own  
Responses: **200** OK, **401** Unauthorized, **404** (user) Not Found

`POST /frequest/<UID>` - Send a friend request to another user  
```json
{
    "playerID": <UID>
}
```
Responses: **200** OK, **401** Unauthorized, **404** (user) Not Found

`GET /status` - Check service status  
Responses: **200** OK, **503** Service Unavailable

<br>

### Game Service endpoints:  
`GET /lobby` - Get a list of available lobbies  
Responses: **200** OK, **401** Unauthorized, **404** (lobby) Not Found

`POST /lobby/make` - Create a new lobby
```json
{
    "playerID": <UID>
}
```
Responses: **200** OK, **401** Unauthorized

`GET /lobby/<LID>` - Get information about a particular lobby  
Responses: **200** OK, **401** Unauthorized

`POST /lobby/<LID>/join` - Join a specific lobby  
```json
{
    "playerID": <UID>
}
```
Responses: **200** OK, **401** Unauthorized, **404** (lobby) Not Found


`GET /lobby/<LID>/leave` - Leave a lobby you're currently in  
Responses: **200** OK, **401** Unauthorized, **404** (lobby) Not Found

`GET /game/<GID>` - Get information about a particular game (Province ownership, active units, etc.)  
Responses: **200** OK, **401** Unauthorized, **404** (game) Not Found, **429** Too Many Requests

A Websocket connection would be established as soon as players would connect to a game, as to keep players updated in real-time with any actions performed by others. Data being sent would have an ID that would correspond with the action performed, to prevent ambiguities.

When a player chooses a policy to affect his nation, only the ID of the policy would be required to be sent:
```js
data: {
    "actionID": 1,
    "policyID": <int>
}
```

If a player wants to upgrade a province:
```js
data: {
    "actionID": 2,
    "provinceID": <int>,
    "upgradeID": <int>
}
```


If a player chooses a diplomatic action (requesting alliance, signing a non-aggression pact, declaring war, etc.), the target player is required as well:
```js
data: {
    "actionID": 3,
    "targetPlayer": <UID>,
    "diploID": <int>
}
```

The same goes if a player wants to perform a resource trade with another:
```js
data: JSON.stringify({
    "actionID": 4,
    "targetPlayer": <UID>,
    "tradeSendItems": [<int>],
    "tradeSendQty": [<int>],
    "tradeGetItems": [<int>],
    "tradeGetQty": [<int>],
    "yearlyRate": <bool>
})
```

If a player wishes to create a unit:
```js
data: {
    "actionID": 5,
    "unitTypes": [<int>],
    "unitIDs": [<int>]
}
```

And lastly, if a player wants to send a message to another:
```js
{
    "actionID": 6,
    "targetPlayer": <UID>,
    "messageBody": <string>
}
```

The above should cover most actions a player may perform during a session within the game that would require other players to be aware of.

`GET /status` - Check service status  
Responses: **200** OK, **503** Service Unavailable




All requests that may return Error **401**, except for `POST /login`, require a bearer authorization token in their request headers, as they can only be performed successfully once logged in

## Deployement & Scaling
Each service, database and cache will each run in a corresponding Docker container. Orchestration will be performed by Kubernetes and tested locally using Minikube.