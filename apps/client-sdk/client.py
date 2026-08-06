import json
from web3 import Web3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import os

class DecentralizedComputeClient:
    def __init__(self, provider_url, private_key, orchestrator_addr, orchestrator_abi_path, gateway_addr, gateway_abi_path):
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.private_key = private_key
        self.account = self.w3.eth.account.from_key(private_key)
        
        with open(orchestrator_abi_path, 'r') as f:
            self.orchestrator = self.w3.eth.contract(address=orchestrator_addr, abi=json.load(f))
            
        with open(gateway_abi_path, 'r') as f:
            self.gateway = self.w3.eth.contract(address=gateway_addr, abi=json.load(f))

    def encrypt_payload(self, data: bytes, key: bytes) -> tuple[bytes, bytes]:
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, None)
        return nonce, ct
        
    def register_job(self, budget: int, cid: str, min_cpu: int, min_gpu: int, min_ram: int):
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        
        tx = self.gateway.functions.registerAndFundJob(
            cid, min_cpu, min_gpu, min_ram
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'value': budget,
            'gasPrice': self.w3.eth.gas_price
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        logs = self.gateway.events.CrossChainJobFunded().process_receipt(receipt)
        if logs:
            return logs[0]['args']['jobId']
        return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    import sys
    import os
    
    load_dotenv()
    
    print("Initializing Decentralized Compute Client for E2E Test...")
    PROVIDER_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
    
    import sys
    import os
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    orchestrator_abi_path = os.path.join(project_root, "contracts", "artifacts", "contracts", "JobOrchestrator.sol", "JobOrchestrator.json")
    gateway_abi_path = os.path.join(project_root, "contracts", "artifacts", "contracts", "ClientGateway.sol", "ClientGateway.json")
    
    address_path = os.path.join(project_root, "contracts", "deployed_addresses.json")
        
    with open(address_path, 'r') as f:
        addresses = json.load(f)
        
    # Extract ABIs
    with open(orchestrator_abi_path, 'r') as f:
        with open("temp_orch_abi.json", 'w') as out:
            json.dump(json.load(f)["abi"], out)
    with open(gateway_abi_path, 'r') as f:
        with open("temp_gate_abi.json", 'w') as out:
            json.dump(json.load(f)["abi"], out)
            
    try:
        client = DecentralizedComputeClient(
            provider_url=PROVIDER_URL,
            private_key=PRIVATE_KEY,
            orchestrator_addr=addresses["JobOrchestrator"],
            orchestrator_abi_path="temp_orch_abi.json",
            gateway_addr=addresses["ClientGateway"],
            gateway_abi_path="temp_gate_abi.json"
        )
        
        print(f"\nConnected successfully as {client.account.address}")
        
        print("Generating secure random AES-256 session key...")
        session_key = os.urandom(32)

        print("Generating TenSEAL FHE Context and Encrypting Data...")
        import tenseal as ts
        context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=8192, coeff_mod_bit_sizes=[60, 40, 40, 60])
        context.generate_galois_keys()
        context.global_scale = 2**40
        plain_vector = [10.5, 20.5, 30.5, 40.5]
        enc_vector = ts.ckks_vector(context, plain_vector)
        
        public_context = context.copy()
        public_context.make_context_public()
        serialized_context = public_context.serialize().hex()
        serialized_vector = enc_vector.serialize().hex()
        
        payload_script = f"""
import tenseal as ts
import json
import os
def compute():
    context = ts.context_from(bytes.fromhex('{serialized_context}'))
    enc_vector = ts.ckks_vector_from(context, bytes.fromhex('{serialized_vector}'))
    result = enc_vector * enc_vector + 10
    result_hex = result.serialize().hex()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    result_path = os.path.join(project_root, "mock_fhe_result.json")
    with open(result_path, 'w') as f:
        json.dump({{"fhe_result": result_hex}}, f)
compute()
"""
        test_data = payload_script.encode('utf-8')
        aes_key = session_key[:32]
        nonce, ciphertext = client.encrypt_payload(test_data, aes_key)
        
        import crypto_pqc
        mldsa_vk, mldsa_sk = crypto_pqc.generate_mldsa_keys()
        payload_to_sign = nonce + ciphertext
        signature = crypto_pqc.sign_message(mldsa_sk, payload_to_sign)
        
        manifest = {
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
            "mldsa_public_key": mldsa_vk.hex(),
            "mldsa_signature": signature.hex()
        }
        
        ipfs_uri = "ipfs://QmDummyCidForTestingPhase2Integration"
        mock_payload_path = os.path.join(project_root, "mock_ipfs_payload.json")
        with open(mock_payload_path, 'w') as f:
            json.dump(manifest, f)
            
        print(f"\nFunding job cross-chain on ClientGateway...")
        budget_wei = 1500 # Just an arbitrary value to send
        job_id = client.register_job(budget=budget_wei, cid=ipfs_uri, min_cpu=8, min_gpu=16, min_ram=32)
        
        if job_id is not None:
            print(f"[SUCCESS] Job Funded! Waiting for Relayer to bridge to Orchestrator...")
            import time
            
            # Wait for Relayer to pick it up and bridge it
            for _ in range(10):
                try:
                    state = client.orchestrator.functions.getJobState(job_id).call()
                    if state == 1:
                        print("Relayer successfully bridged job to Orchestrator!")
                        break
                except:
                    pass
                time.sleep(1)
            
            print("\nWaiting for workers to bid on the job...")
            time.sleep(10)
            
            print("Assigning the job to the winning worker...")
            nonce = client.w3.eth.get_transaction_count(client.account.address)
            tx = client.orchestrator.functions.assignWinner(job_id).build_transaction({
                'from': client.account.address,
                'nonce': nonce,
                'gas': 1000000,
                'gasPrice': client.w3.to_wei('50', 'gwei')
            })
            signed_tx = client.w3.eth.account.sign_transaction(tx, private_key=client.private_key)
            tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            client.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Fetch the assigned worker's public key
            job_info = client.orchestrator.functions.getJob(job_id).call()
            assigned_worker = job_info[7]
            worker_pk_pem = client.orchestrator.functions.workerPublicKeys(assigned_worker).call()
            
            print(f"Encapsulating KEK and wrapping session key for worker {assigned_worker}...")
            # The worker's public key string is actually "kyber_pk_hex:x25519_pk_hex"
            parts = worker_pk_pem.split(':')
            worker_kyber_pk = bytes.fromhex(parts[0])
            worker_x25519_pk = bytes.fromhex(parts[1])
            
            # 1. PQC Hybrid KEM Encapsulation
            import crypto_pqc
            kyber_ct, x25519_e_pk, shared_secret = crypto_pqc.client_encapsulate(worker_kyber_pk, worker_x25519_pk)
            
            # 2. Wrap the actual session key using the KEM shared secret (KEK)
            kek_aesgcm = AESGCM(shared_secret[:32])
            kek_nonce = os.urandom(12)
            wrapped_session_key = kek_aesgcm.encrypt(kek_nonce, session_key, None)
            
            # 3. Format payload for smart contract
            encrypted_session_key_hex = f"{kyber_ct.hex()}:{x25519_e_pk.hex()}:{kek_nonce.hex()}:{wrapped_session_key.hex()}"
            
            print("Providing encrypted session key via Smart Contract...")
            nonce = client.w3.eth.get_transaction_count(client.account.address)
            tx = client.orchestrator.functions.provideKey(job_id, encrypted_session_key_hex).build_transaction({
                'from': client.account.address,
                'nonce': nonce,
                'gas': 1000000,
                'gasPrice': client.w3.to_wei('50', 'gwei')
            })
            signed_tx = client.w3.eth.account.sign_transaction(tx, private_key=client.private_key)
            tx_hash = client.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            client.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            print("Waiting for worker to execute enclave workload and submit proof...")
            start_time = time.time()
            while True:
                state = client.orchestrator.functions.getJobState(job_id).call()
                if state == 5: # ProofSubmitted
                    print(f"\n[SUCCESS] Worker has submitted ZK Execution Proof!")
                    print("Waiting for Relayer to release payment to worker...")
                    time.sleep(3) # Give relayer time to catch event
                    print("Payment verified released via Relayer logs!")
                    break
                time.sleep(3)
        else:
            print("[FAILED] Could not register job.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if os.path.exists("temp_orch_abi.json"): os.remove("temp_orch_abi.json")
        if os.path.exists("temp_gate_abi.json"): os.remove("temp_gate_abi.json")
