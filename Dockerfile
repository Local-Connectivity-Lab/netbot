# Use a Python image with uv pre-installed
# see https://docs.astral.sh/uv/guides/integration/docker
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Copy the project into the image
ADD . /app

# Install the project into `/app`
WORKDIR /app
RUN uv sync

# Run netbot
CMD ["uv", "run", "-m", "netbot.netbot"]

# to enable debug logging
#CMD ["uv", "run", "-m", "netbot.netbot", "debug"]
