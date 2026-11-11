FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2.8-alpine
COPY --from=build /web/dist /srv
COPY Caddyfile.static /etc/caddy/Caddyfile
EXPOSE 80
