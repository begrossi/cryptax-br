FROM node:24-alpine AS builder
WORKDIR /app
RUN npm install -g pnpm
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile --ignore-scripts || pnpm install --ignore-scripts
COPY . .
ENV BACKEND_URL=http://backend:8000
RUN node_modules/.bin/next build

FROM node:24-alpine
WORKDIR /app
RUN npm install -g pnpm
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
EXPOSE 3000
CMD ["node_modules/.bin/next", "start"]
