# OpenMontage — full production image
# Python tools + Backlot + Node 22 + Remotion + HyperFrames + Mermaid CLI
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BACKLOT_HOST=0.0.0.0 \
    BACKLOT_PORT=4750 \
    VAULT_APP_SLUG=openmontage \
    VAULT_LOAD_SHARED=true \
    NODE_ENV=production \
    # Remotion / Puppeteer-friendly defaults inside containers
    REMOTION_GL=swangle \
    PUPPETEER_CACHE_DIR=/root/.cache/puppeteer

# System packages: ffmpeg, Chrome/Remotion libs, fonts, build tools for native npm
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        gnupg \
        git \
        xz-utils \
        # Remotion headless Chrome dependencies
        chromium \
        fonts-liberation \
        fonts-noto-color-emoji \
        fonts-dejavu-core \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
        libx11-xcb1 \
        libxcb1 \
        libxext6 \
        libx11-6 \
        # Mermaid / Puppeteer extras
        libgtk-3-0 \
        libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 (HyperFrames requires >= 22)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

# Prefer system Chromium for Puppeteer-based tools when applicable
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    CHROME_PATH=/usr/bin/chromium

WORKDIR /app

COPY requirements.txt setup.py ./
COPY lib/ ./lib/
COPY tools/ ./tools/
COPY backlot/ ./backlot/
COPY schemas/ ./schemas/
COPY styles/ ./styles/
COPY pipeline_defs/ ./pipeline_defs/
COPY skills/ ./skills/
COPY .agents/skills/ ./.agents/skills/
COPY docs/feature/gpu-ai-integration/ ./docs/feature/gpu-ai-integration/
COPY config.yaml ./
COPY scripts/ ./scripts/
COPY remotion-composer/ ./remotion-composer/

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -e . \
    && mkdir -p /app/projects /app/output /app/.backlot

# Remotion project deps + Chrome for @remotion/renderer
WORKDIR /app/remotion-composer
RUN npm install --no-audit --no-fund \
    && npx remotion browser ensure || true \
    && test -d node_modules

# Global CLIs used by OpenMontage tools
WORKDIR /app
RUN npm install -g --no-audit --no-fund @mermaid-js/mermaid-cli \
    && mmdc --version \
    # Warm HyperFrames CLI into npx cache (package name on npm is `hyperframes`)
    && npx --yes hyperframes --version \
    && node --version \
    && which npx ffmpeg mmdc

EXPOSE 4750

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${BACKLOT_PORT}/api/health" || exit 1

CMD ["python", "-m", "backlot", "serve", "--host", "0.0.0.0", "--port", "4750"]
