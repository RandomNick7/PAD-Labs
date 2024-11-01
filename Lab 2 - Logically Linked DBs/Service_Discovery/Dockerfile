FROM node:23

WORKDIR /app

CMD ["npm", "start"]

COPY package.json /app
RUN npm install --force --loglevel

COPY . /app

EXPOSE 4444

CMD ["node", "index.js"]