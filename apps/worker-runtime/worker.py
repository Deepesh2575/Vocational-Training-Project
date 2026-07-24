import json
import time
import os
import hashlib
import sys
from web3 import Web3

# Ensure we can import crypto_pqc (assumes the module is installed in the current venv)
try:
    import crypto_pqc
except ImportError:
    print("Error: crypto_pqc module not found. Did you compile the Rust library using maturin?")
    sys.exit(1)

class ConfidentialWorkerNode:
    def __init__(self, provider_url, private_key, contract_address, contract_abi_path):
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.private_key = private_key
        self.account = self.w3.eth.account.from_key(private_key)
        
        with open(contract_abi_path, 'r') as f:
            abi = json.load(f)
            
        self.contract = self.w3.eth.contract(address=contract_address, abi=abi)
        print(f"Worker Node Initialized: {self.account.address}")
        
        # Worker capabilities
        self.cpu = 16
        self.gpuVram = 32
        self.ram = 64
        self.stake = self.w3.to_wei(1, 'ether') # 1 ETH stake for MVP

    def submit_bid(self, job_id: int):
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        tx = self.contract.functions.submitBid(
            job_id, self.stake, self.cpu, self.gpuVram, self.ram
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 1000000,
            'gasPrice': self.w3.to_wei('50', 'gwei')
        })
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Bid submitted for Job ID {job_id} with stake {self.w3.from_wei(self.stake, 'ether')} ETH.")

    def mark_executing(self, job_id: int):
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        tx = self.contract.functions.markExecuting(job_id).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 1000000,
            'gasPrice': self.w3.to_wei('50', 'gwei')
        })
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Marked Job ID {job_id} as Executing.")

    def submit_proof(self, job_id: int, proof_hash: bytes):
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        tx = self.contract.functions.submitProof(job_id, proof_hash).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 1000000,
            'gasPrice': self.w3.to_wei('50', 'gwei')
        })
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Submitted ZK Proof for Job ID {job_id}.")

    def simulate_execution(self, job_id: int):
        print(f"\n--- [TEE Enclave] Executing Job ID {job_id} ---")
        time.sleep(2) # Simulate compute delay
        
        # In a real environment, the worker would:
        # 1. Decapsulate the session key using worker_encapsulate.
        # 2. Decrypt the payload (AES-GCM).
        # 3. Execute the payload logic inside the TEE.
        # 4. Generate a ZK proof of deterministic execution.
        
        print("Compute workload finished successfully.")
        
        # Produce a simulated ZK Proof / Result Hash
        result_str = f"Result of Job {job_id}: Success!"
        proof_hash = hashlib.sha256(result_str.encode()).digest()
        print(f"Generated Result Hash: {proof_hash.hex()}")
        return proof_hash

    def poll_for_jobs(self):
        print("Listening for jobs on the smart contract...")
        processed_jobs = set()
        
        while True:
            # We assume a simplistic setup where job IDs increment from 0.
            # In production, we'd use event filters.
            
            # Find the highest job ID currently registered by probing getJobState
            # (In a real app we'd fetch events, but for MVP we just loop starting from 0)
            
            for job_id in range(100):
                try:
                    state = self.contract.functions.getJobState(job_id).call()
                    
                    if state == 1 and job_id not in processed_jobs: # BiddingOpen
                        print(f"\n[Worker] Found Job {job_id} in BiddingOpen state.")
                        
                        # Inspect job requirements
                        job_info = self.contract.functions.getJob(job_id).call()
                        min_cpu, min_gpu, min_ram = job_info[3], job_info[4], job_info[5]
                        
                        if self.cpu >= min_cpu and self.gpuVram >= min_gpu and self.ram >= min_ram:
                            print("[Worker] Capabilities match. Submitting bid...")
                            self.submit_bid(job_id)
                            processed_jobs.add(job_id)
                            
                except Exception as e:
                    # Job ID probably doesn't exist yet, break out of loop
                    if "execution reverted" in str(e) or "out of bounds" in str(e) or type(e) == IndexError:
                        pass
                        
            # Check if any processed job was assigned to us
            for job_id in list(processed_jobs):
                try:
                    state = self.contract.functions.getJobState(job_id).call()
                    if state == 2: # Assigned
                        job_info = self.contract.functions.getJob(job_id).call()
                        assigned_worker = job_info[7]
                        
                        if assigned_worker == self.account.address:
                            print(f"\n[Worker] Assigned to Job {job_id}!")
                            self.mark_executing(job_id)
                            proof_hash = self.simulate_execution(job_id)
                            self.submit_proof(job_id, proof_hash)
                            processed_jobs.remove(job_id) # Done
                        else:
                            print(f"\n[Worker] Job {job_id} assigned to a different worker.")
                            processed_jobs.remove(job_id) # We lost the bid
                except Exception:
                    pass
                    
            time.sleep(3)


if __name__ == "__main__":
    print("Starting Confidential Worker Node...")
    
    PROVIDER_URL = "http://127.0.0.1:8545"
    
    # Account #1 from Hardhat local node (Worker identity)
    PRIVATE_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    abi_path = os.path.join(
        project_root, 
        "contracts", "artifacts", "contracts", "JobOrchestrator.sol", "JobOrchestrator.json"
    )
    
    contract_address = input("Enter the deployed JobOrchestrator contract address: ").strip()
    
    if not contract_address:
        print("Invalid address. Exiting.")
        sys.exit(1)
        
    # Extract ABI if full artifact provided
    temp_abi_path = "worker_temp_abi.json"
    with open(abi_path, 'r') as f:
        artifact = json.load(f)
        with open(temp_abi_path, 'w') as temp_f:
            json.dump(artifact.get("abi", artifact), temp_f)

    worker = ConfidentialWorkerNode(
        provider_url=PROVIDER_URL,
        private_key=PRIVATE_KEY,
        contract_address=contract_address,
        contract_abi_path=temp_abi_path
    )
    
    try:
        worker.poll_for_jobs()
    except KeyboardInterrupt:
        print("\nWorker shutting down.")
    finally:
        if os.path.exists(temp_abi_path):
            os.remove(temp_abi_path)
