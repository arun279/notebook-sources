# syntax=docker/dockerfile:1

FROM node:20-alpine AS base

WORKDIR /app

# Install dependencies first (leverages Docker layer cache)
COPY package.json ./
RUN npm install --no-audit --no-fund --verbose

# Copy source
COPY . .

# Default command runs Vite dev server accessible on port 3000.
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]