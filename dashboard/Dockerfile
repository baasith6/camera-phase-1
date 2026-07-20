# Stage 1 — build the Angular app
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --prefer-offline
COPY . .
RUN npm run build -- --configuration production

# Stage 2 — serve with nginx
FROM nginx:1.25-alpine
COPY --from=build /app/dist/dashboard/browser /usr/share/nginx/html
# Custom nginx config: proxy /api → backend, serve Angular SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
