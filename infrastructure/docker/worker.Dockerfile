FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for building TenSEAL and crypto libs
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Create virtual environment (maturin requires one)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install maturin
RUN pip install maturin

# Copy crypto module and compile
COPY crypto/pqc /app/crypto/pqc
WORKDIR /app/crypto/pqc
RUN maturin build --release
RUN pip install target/wheels/*.whl

WORKDIR /app

# Copy requirements and install python packages
COPY apps/worker-runtime/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install python-dotenv

# Copy the worker application code
COPY apps/worker-runtime/ /app/worker-runtime/
# Copy shared mock files and deployed addresses (mocking shared persistent volume)
COPY contracts/deployed_addresses.json /app/contracts/
COPY contracts/artifacts /app/contracts/artifacts

WORKDIR /app/worker-runtime

# Start the worker daemon
CMD ["python", "-u", "worker.py"]
