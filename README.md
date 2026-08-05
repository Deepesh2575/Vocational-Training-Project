# Decentralized Compute Network - Local E2E Demo

This guide explains how to run the entire project locally, incorporating all phases of the architecture (Smart Contracts, ZK Proofs, FHE, Governance, and Cross-Chain Relayer).

Because this is a distributed system with multiple independent actors, you will need to open **4 separate terminal windows** to run the demo effectively. This allows you to see the real-time logs of the Relayer, the Worker, and the Client simultaneously.

---

### Prerequisites
Make sure you have activated your Python virtual environment in each terminal before running the python scripts:
```powershell
.venv\Scripts\activate
```

---

### Terminal 1: Local Blockchain & Deployment
First, start the local Hardhat node. This simulates our blockchain network.
1. Open a terminal and navigate to the `contracts/` directory:
   ```powershell
   cd contracts
   ```
2. Start the local node:
   ```powershell
   npx hardhat node
   ```
*(Leave this terminal running. It will log all blockchain transactions.)*

**In a new terminal tab**, deploy the smart contracts to the local node:
```powershell
cd contracts
npx hardhat run scripts/deploy.ts --network localhost
```
*This deploys the ClientGateway, JobOrchestrator, Governance, and ZK Verifier contracts, and saves their addresses.*

---

### Terminal 2: The Cross-Chain Relayer
The relayer simulates a bridge (like LayerZero). It listens for events on the ClientGateway and bridges them to the JobOrchestrator.
1. Open a new terminal and navigate to the `apps/relayer` directory.
2. Activate your virtual environment if you haven't already.
3. Run the daemon:
   ```powershell
   python -u relayer.py
   ```
*(Leave this terminal running. It will wait silently until the client funds a job.)*

---

### Terminal 3: The Worker Node
The worker node listens for new jobs, bids on them, executes the FHE computation securely, and generates ZK Proofs.
1. Open a new terminal and navigate to the `apps/worker-runtime` directory.
2. Activate your virtual environment if you haven't already.
3. Run the daemon:
   ```powershell
   python -u worker.py
   ```
*(Leave this terminal running. It will say "Listening for jobs...")*

---

### Terminal 4: The Client
Finally, run the client script. The client will encrypt the payload using Fully Homomorphic Encryption (FHE), upload it to a mock IPFS, fund the job on the cross-chain gateway, and wait for the results.
1. Open a new terminal and navigate to the `apps/client-sdk` directory.
2. Activate your virtual environment if you haven't already.
3. Run the client:
   ```powershell
   python -u client.py
   ```

### What you will see:
1. The **Client** will print its FHE encryption process and fund the job.
2. The **Relayer** terminal will detect the funding and bridge it to the Orchestrator.
3. The **Worker** terminal will detect the job, bid on it, and (once assigned) execute the FHE computation and submit a ZK-SNARK proof.
4. The **Relayer** will detect the ZK-SNARK proof and release the payment on the Gateway.
5. The **Client** will see the completion, retrieve the encrypted result, and decrypt it successfully!
