FROM node:26-alpine AS build
WORKDIR /app

ARG VITE_SENTRY_DSN=""
ARG VITE_SENTRY_ENVIRONMENT="development"
# "online" builds the public radar-online dashboard; empty builds the local one.
ARG VITE_RADAR_MODE=""
ENV VITE_SENTRY_DSN=${VITE_SENTRY_DSN}
ENV VITE_SENTRY_ENVIRONMENT=${VITE_SENTRY_ENVIRONMENT}
ENV VITE_RADAR_MODE=${VITE_RADAR_MODE}

COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
RUN apk update && apk upgrade --no-cache
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
