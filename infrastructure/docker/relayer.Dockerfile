FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY apps/worker-runtime/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the relayer daemon code
COPY apps/relayer/ /app/relayer/
# Copy the required ABI and address JSONs
COPY contracts/deployed_addresses.json /app/contracts/
COPY contracts/artifacts /app/contracts/artifacts

WORKDIR /app/relayer

# Start the relayer daemon
CMD ["python", "-u", "relayer.py"]
