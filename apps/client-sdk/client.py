import json
from web3 import Web3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class DecentralizedComputeClient:
    def __init__(self, provider_url, private_key, contract_address, contract_abi_path):
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.private_key = private_key
        self.account = self.w3.eth.account.from_key(private_key)
        
        with open(contract_abi_path, 'r') as f:
            abi = json.load(f)
            
        self.contract = self.w3.eth.contract(address=contract_address, abi=abi)

    def encrypt_payload(self, data: bytes, key: bytes) -> tuple[bytes, bytes]:
        """
        Encrypts a payload using AES-256-GCM as specified in the blueprint.
        """
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, None)
        return nonce, ct
        
    def register_job(self, budget: int, cid: str, min_cpu: int, min_gpu: int, min_ram: int):
        """
        Registers a job on the smart contract.
        """
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        
        tx = self.contract.functions.registerJob(
            budget, cid, min_cpu, min_gpu, min_ram
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 2000000,
            'gasPrice': self.w3.to_wei('50', 'gwei')
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Parse the logs to get the job ID
        logs = self.contract.events.JobRegistered().process_receipt(receipt)
        if logs:
            job_id = logs[0]['args']['jobId']
            return job_id
        return None

if __name__ == "__main__":
    # E2E Test against a local Hardhat node
    print("Initializing Decentralized Compute Client for E2E Test...")
    
    # Default Hardhat local node URL
    PROVIDER_URL = "http://127.0.0.1:8545"
    
    # Account #0 from Hardhat local node (DO NOT USE IN PRODUCTION)
    PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    
    # To run this, you must first deploy the contract to your local hardhat node.
    # We load the ABI from the hardhat artifacts directory.
    import sys
    import os
    
    # Path to the compiled ABI
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    abi_path = os.path.join(
        project_root, 
        "contracts", "artifacts", "contracts", "JobOrchestrator.sol", "JobOrchestrator.json"
    )
    
    if not os.path.exists(abi_path):
        print(f"Error: ABI not found at {abi_path}")
        print("Please compile the contracts first by running `npx hardhat compile` inside the 'contracts' directory.")
        sys.exit(1)
        
    # Ask the user for the deployed contract address
    print("Please ensure you have started a local node (`npx hardhat node`) and deployed the contract (`npx hardhat run scripts/deploy.ts --network localhost`).")
    contract_address = input("Enter the deployed JobOrchestrator contract address: ").strip()
    
    if not contract_address:
        print("Invalid address. Exiting.")
        sys.exit(1)
        
    try:
        # Load just the ABI portion from the Hardhat artifact
        with open(abi_path, 'r') as f:
            artifact = json.load(f)
            # Write a temporary ABI file since our client constructor expects a raw ABI file
            temp_abi_path = "temp_abi.json"
            with open(temp_abi_path, 'w') as temp_f:
                json.dump(artifact["abi"], temp_f)
                
        client = DecentralizedComputeClient(
            provider_url=PROVIDER_URL,
            private_key=PRIVATE_KEY,
            contract_address=contract_address,
            contract_abi_path=temp_abi_path
        )
        
        print(f"\nConnected successfully as {client.account.address}")
        
        # True Hybrid PQC Handshake
        print("Performing True Hybrid Post-Quantum Key Exchange...")
        import crypto_pqc
        
        # 1. Generate real client keys
        client_kyber_pk, client_kyber_sk, client_x25519_pk, client_x25519_sk = crypto_pqc.generate_client_keys()
        
        # 2. Simulate worker encapsulation
        worker_kyber_ct, worker_x25519_pk = crypto_pqc.worker_encapsulate(client_kyber_pk, client_x25519_pk)
        
        # 3. Client decapsulates to derive session key
        session_key = crypto_pqc.client_decapsulate(worker_kyber_ct, worker_x25519_pk, client_kyber_sk, client_x25519_sk)
        
        print(f"Post-Quantum Session Key Derived: {session_key.hex()[:16]}... (64 bytes)")

        # Test Payload Encryption
        print("\nTesting Payload Encryption (AES-256-GCM)...")
        test_data = b"Hello Confidential Compute Enclave!"
        # AES-256 requires exactly a 32-byte key. We take the first 32 bytes of the 64-byte derived session key.
        aes_key = session_key[:32]
        nonce, ciphertext = client.encrypt_payload(test_data, aes_key)
        print(f"Encrypted! Nonce: {nonce.hex()}, Ciphertext: {ciphertext.hex()}")
        
        # Test Job Registration
        print("\nRegistering a job on the local blockchain...")
        job_id = client.register_job(
            budget=1500,
            cid="ipfs://QmTest123",
            min_cpu=8,
            min_gpu=16,
            min_ram=32
        )
        
        if job_id is not None:
            print(f"[SUCCESS] Job successfully registered with ID: {job_id}")
            # Fetch the job state to verify
            state = client.contract.functions.getJobState(job_id).call()
            print(f"Current Job State (0=Created, 1=BiddingOpen): {state}")
            
            print("\nWaiting for workers to bid on the job...")
            # Wait for 10 seconds to allow the worker script to bid
            import time
            time.sleep(5)
            
            print("Assigning the job to the winning worker...")
            nonce = client.w3.eth.get_transaction_count(client.account.address)
            tx = client.contract.functions.assignWinner(job_id).build_transaction({
                'from': client.account.address,
                'nonce': nonce,
                'gas': 1000000,
                'gasPrice': client.w3.to_wei('50', 'gwei')
            })
            signed_tx = client.w3.eth.account.sign_transaction(tx, private_key=client.private_key)
            tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            client.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            job_info = client.contract.functions.getJob(job_id).call()
            print(f"Job assigned to Worker: {job_info[7]}")
            
            print("Waiting for worker to execute enclave workload and submit proof...")
            # Poll for completion
            while True:
                state = client.contract.functions.getJobState(job_id).call()
                if state == 4: # ProofSubmitted
                    job_info = client.contract.functions.getJob(job_id).call()
                    print(f"\n[SUCCESS] Worker has submitted ZK Execution Proof!")
                    print(f"Result Hash: {job_info[8].hex()}")
                    break
                time.sleep(3)
            
        else:
            print("[FAILED] Could not register job.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup
        if os.path.exists("temp_abi.json"):
            os.remove("temp_abi.json")
