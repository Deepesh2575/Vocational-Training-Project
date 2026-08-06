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

# Install Circom (from source using cargo)
RUN git clone https://github.com/iden3/circom.git /tmp/circom && \
    cd /tmp/circom && \
    cargo build --release && \
    cargo install --path circom

# Install Node.js & SnarkJS for ZK Proof generation
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g snarkjs

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

# Compile ZK-SNARK Circuit and Perform Trusted Setup
RUN cd circuits && \
    circom multiplier.circom --r1cs --wasm --sym && \
    snarkjs powersoftau new bn128 12 pot12_0000.ptau -v && \
    snarkjs powersoftau contribute pot12_0000.ptau pot12_0001.ptau --name="First contribution" -v -e="random text" && \
    snarkjs powersoftau prepare phase2 pot12_0001.ptau pot12_final.ptau -v && \
    snarkjs groth16 setup multiplier.r1cs pot12_final.ptau multiplier_0000.zkey && \
    snarkjs zkey contribute multiplier_0000.zkey multiplier_final.zkey --name="Docker Build Contribution" -v -e="random docker entropy" && \
    snarkjs zkey export verificationkey multiplier_final.zkey verification_key.json

# Start the worker daemon
CMD ["python", "-u", "worker.py"]
