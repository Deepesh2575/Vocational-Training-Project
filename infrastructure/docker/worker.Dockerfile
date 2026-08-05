FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for building TenSEAL and crypto libs
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY apps/worker-runtime/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker application code
COPY apps/worker-runtime/ /app/worker-runtime/
# Copy shared mock files and deployed addresses (mocking shared persistent volume)
COPY contracts/deployed_addresses.json /app/contracts/
COPY contracts/artifacts /app/contracts/artifacts

WORKDIR /app/worker-runtime

# Start the worker daemon
CMD ["python", "-u", "worker.py"]
