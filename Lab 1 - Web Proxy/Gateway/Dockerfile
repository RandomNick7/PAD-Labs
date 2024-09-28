# Using a base image with Node
FROM node:22
WORKDIR /app
COPY . .
RUN npm install
EXPOSE 6969
CMD ["node", "index.js"]