# Stage 1 — build the React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG VITE_API_ENDPOINT
ARG VITE_P2A_API_ENDPOINT
ARG VITE_AI_ENDPOINT
ENV VITE_API_ENDPOINT=$VITE_API_ENDPOINT
ENV VITE_P2A_API_ENDPOINT=$VITE_P2A_API_ENDPOINT
ENV VITE_AI_ENDPOINT=$VITE_AI_ENDPOINT

RUN npm run build

# Stage 2 — serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
