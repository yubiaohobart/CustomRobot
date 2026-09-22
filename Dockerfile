# Multi-stage Dockerfile for Node.js Full-Stack IntelliServe Customer Service System

# 1. Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application source code
COPY . .

# Build Vite frontend & Bundle Express server.ts to dist/server.cjs
RUN npm run build

# 2. Production runtime stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

# Copy built artifacts and production dependencies
COPY package.json ./
RUN npm install --omit=dev

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/public ./public

# Expose standard port
EXPOSE 3000

# Start server
CMD ["node", "dist/server.cjs"]
