FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libasound2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Récupère le dernier binaire précompilé depuis les releases GitHub
RUN curl -L -o /tmp/librespot.tar.gz \
    https://github.com/librespot-org/librespot/releases/latest/download/librespot-linux-amd64.tar.gz \
    && tar -xzf /tmp/librespot.tar.gz -C /usr/local/bin \
    && chmod +x /usr/local/bin/librespot \
    && rm /tmp/librespot.tar.gz

ENTRYPOINT ["librespot"]
