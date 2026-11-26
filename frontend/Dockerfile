FROM node:22.14.0-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY index.html tsconfig.json *.config.ts ./
COPY src ./src
COPY tests ./tests
COPY public ./public
# Browser requests use the nginx origin; no environment files or secrets enter dist.
ENV VITE_SEARCH_MODE=api VITE_API_BASE_URL=""
RUN npm run build

FROM nginx:1.28-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
