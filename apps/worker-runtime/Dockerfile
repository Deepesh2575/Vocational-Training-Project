# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Also install Node.js and snarkjs globally (required for ZK Prover)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g snarkjs circom && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code
COPY . .

# Run worker.py when the container launches
CMD ["python", "worker.py"]
