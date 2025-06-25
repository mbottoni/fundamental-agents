# Stage 1: Build the application
FROM node:18-alpine AS builder
WORKDIR /app

# Copy package configuration and install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the application source code
COPY . .

# Build the Next.js application for production
RUN npm run build

# Stage 2: Create the production image
FROM node:18-alpine
WORKDIR /app

# Copy built assets from the builder stage
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# Expose the port the app runs on
EXPOSE 3000

# Start the Next.js production server
CMD ["npm", "start"] 