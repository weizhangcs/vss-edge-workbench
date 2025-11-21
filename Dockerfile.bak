# Dockerfile

# 1. Use the official Python 3.12 image as a base
FROM python:3.12-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1  # Prevents python from creating .pyc files
ENV PYTHONUNBUFFERED 1         # Ensures Python output is directly visible in Docker logs

# 3. Conditionally switch to a domestic APT source and install dependencies
#    Declare a build argument named APT_MIRROR with an empty default value
ARG APT_MIRROR

#    Only execute the sed command to replace the source if the APT_MIRROR argument is provided
RUN if [ -n "$APT_MIRROR" ]; then \
        echo "Using APT mirror: $APT_MIRROR" && \
        sed -i "s|deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 4. Set the working directory
WORKDIR /app

# 5. Copy and install Python dependencies using a configurable PIP source
COPY requirements.txt .

# Declare a build argument for the pip index URL
ARG PIP_MIRROR_URL

# Use the mirror if the argument is provided, otherwise use the default pip index
RUN pip install --no-cache-dir ${PIP_MIRROR_URL:+-i "$PIP_MIRROR_URL"} -r requirements.txt

# 6. Copy the project source code last
#    This is the most frequently changed part, placing it last maximizes the use of all previous layer caches
COPY . .