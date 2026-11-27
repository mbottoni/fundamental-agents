# syntax=docker/dockerfile:1
#
# Two images from one file:
#   dev   what `make up` runs: `next dev` with the source bind-mounted.
#   prod  what is deployed: the standalone server, as an unprivileged user.
#         It is the last stage, so a plain `docker build` produces it.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# `npm ci`, not `npm install`: the lockfile is what CI tested.
RUN npm ci


FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]


FROM deps AS builder
COPY . .
# Next.js writes NEXT_PUBLIC_* values into the bundle while it builds; setting
# them on the running container does nothing. The API is served from the same
# hostname as the site (see the Caddyfile), so the address is a path and this
# one image works on any domain.
ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build


FROM node:22-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
# next/image resizes with sharp. The standalone trace includes the package;
# Next still has to be told where it is, or it serves originals unresized
# (the hero image is 2.4 MB) and logs an error on every request.
ENV NEXT_SHARP_PATH=/app/node_modules/sharp
USER node
EXPOSE 3000
CMD ["node", "server.js"]
