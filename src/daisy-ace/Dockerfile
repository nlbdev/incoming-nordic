# Build Daisy ACE
FROM node:buster-slim as runtime

WORKDIR /usr/src/app

COPY ./daisy-ace/package.json .
COPY ./daisy-ace/yarn.lock .

RUN yarn install

COPY ./daisy-ace/config.json .

EXPOSE 80

CMD ["yarn", "start"]