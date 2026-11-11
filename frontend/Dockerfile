# The frontend image (Step 15e, doc 21): Next.js's standalone server, non-root, only the files it needs.
#   docker build -t rag-frontend --build-arg BACKEND_URL=http://api:8010 ./frontend
# BACKEND_URL and HTTPS are used at BUILD time too (next.config.ts: the /api rewrite and the security
# headers), so set them as build arguments for the environment the image is for.

ARG NODE_IMAGE=node:26-slim        # the version in .nvmrc

# ----------------------------------------------------------------------------- dependencies (cached layer)
FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

# ----------------------------------------------------------------------------- build
FROM ${NODE_IMAGE} AS build
WORKDIR /app
ARG BACKEND_URL=http://api:8010
ARG HTTPS=false
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_OUTPUT=standalone NODE_ENV=production BACKEND_URL=${BACKEND_URL} HTTPS=${HTTPS}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# public/ holds static files; git doesn't keep an empty folder, so make sure it exists for the copy below.
RUN mkdir -p public && npm run build

# ----------------------------------------------------------------------------- runtime
FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ARG BACKEND_URL=http://api:8010
ARG HTTPS=false
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0 \
    BACKEND_URL=${BACKEND_URL} HTTPS=${HTTPS}
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/login').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
CMD ["node", "server.js"]
