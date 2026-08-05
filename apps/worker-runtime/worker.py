import json
import time
import os
import hashlib
import sys
import subprocess
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from web3 import Web3
import zk_prover

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
        
        # Generate persistent in-memory identity (PQC Hybrid Keypair)
        print("[Worker] Generating In-Memory Identity (Kyber + X25519)...")
        self.kyber_pk, self.kyber_sk, self.x25519_pk, self.x25519_sk = crypto_pqc.generate_hybrid_keypair()
        
        # Serialize public keys as hex for the smart contract (kyber_pk:x25519_pk)
        self.public_key_string = f"{self.kyber_pk.hex()}:{self.x25519_pk.hex()}"

    def submit_bid(self, job_id: int):
        print(f"[Worker] Generating TEE Enclave Attestation Quote before bidding...")
        # Bind the worker's address into the report data to prevent replay attacks
        user_data = self.account.address.encode('utf-8')
        enclave_quote = self.get_sev_snp_report(user_data)
        
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        tx = self.contract.functions.submitBid(
            job_id, self.stake, self.cpu, self.gpuVram, self.ram, enclave_quote, self.public_key_string
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 1000000,
            'gasPrice': self.w3.to_wei('50', 'gwei'),
            'value': self.stake
        })
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Bid submitted with Enclave Quote for Job ID {job_id} with stake {self.w3.from_wei(self.stake, 'ether')} ETH.")

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

    def submit_proof(self, job_id: int, proof_data: dict):
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        tx = self.contract.functions.submitProof(
            job_id,
            proof_data["a"],
            proof_data["b"],
            proof_data["c"],
            proof_data["inputs"]
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 1000000,
            'gasPrice': self.w3.to_wei('50', 'gwei')
        })
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Submitted ZK-SNARK Proof for Job ID {job_id}.")

    def reclaim_stake(self, job_id: int):
        print(f"Reclaiming stake for Job ID {job_id}...")
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        tx = self.contract.functions.releaseStake(job_id).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 1000000,
            'gasPrice': self.w3.to_wei('50', 'gwei')
        })
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Successfully reclaimed {self.w3.from_wei(self.stake, 'ether')} ETH stake!")

    def simulate_execution(self, job_id: int, cid: str, encrypted_session_key_hex: str):
        print(f"\n--- [TEE Enclave] Executing Job ID {job_id} ---")
        time.sleep(2) # Simulate compute delay
        
        # Verify Payload Provenance via ML-DSA
        print(f"Fetching payload from IPFS CID: {cid}")
        try:
            from storage import StorageClient
            storage_client = StorageClient()
            manifest = storage_client.download_dict(cid)
                
            nonce_bytes = bytes.fromhex(manifest["nonce"])
            ct_bytes = bytes.fromhex(manifest["ciphertext"])
            mldsa_vk = bytes.fromhex(manifest["mldsa_public_key"])
            signature = bytes.fromhex(manifest["mldsa_signature"])
            
            payload = nonce_bytes + ct_bytes
            is_valid = crypto_pqc.verify_signature(mldsa_vk, payload, signature)
            if is_valid:
                print(f"[Worker] ML-DSA Signature Verified Successfully! (Length: {len(signature)} bytes)")
            else:
                print("[Worker] WARNING: ML-DSA Signature Verification Failed!")
        except Exception as e:
            print(f"[Worker] Could not verify ML-DSA signature or fetch from IPFS: {e}")
            if cid == "ipfs://QmDummyCidForTestingPhase2Integration":
                print("[Worker] Using local mock IPFS payload...")
                mock_payload_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "mock_ipfs_payload.json")
                with open(mock_payload_path, 'r') as f:
                    manifest = json.load(f)
                
                nonce_bytes = bytes.fromhex(manifest["nonce"])
                ct_bytes = bytes.fromhex(manifest["ciphertext"])
                mldsa_vk = bytes.fromhex(manifest["mldsa_public_key"])
                signature = bytes.fromhex(manifest["mldsa_signature"])
                
                payload = nonce_bytes + ct_bytes
                is_valid = crypto_pqc.verify_signature(mldsa_vk, payload, signature)
                if is_valid:
                    print(f"[Worker] ML-DSA Signature Verified Successfully from MOCK! (Length: {len(signature)} bytes)")
                else:
                    print("[Worker] WARNING: ML-DSA Signature Verification Failed from MOCK!")
            else:
                print("[Worker] Failed to fetch manifest.")
                return b""
                
        print("Compute workload finished successfully.")
        
        # 1. Decapsulate the session key using our in-memory PQC secret keys
        try:
            parts = encrypted_session_key_hex.split(':')
            if len(parts) != 4:
                raise Exception("Invalid encapsulated key format (expected kyber_ct:x25519_pk:nonce:wrapped_key)")
                
            kyber_ct = bytes.fromhex(parts[0])
            client_x25519_ephemeral_pk = bytes.fromhex(parts[1])
            kek_nonce = bytes.fromhex(parts[2])
            wrapped_session_key = bytes.fromhex(parts[3])
            
            print("[Worker] Decapsulating KEK securely using in-memory PQC Secret Keys...")
            shared_secret = crypto_pqc.worker_decapsulate(
                kyber_ct, client_x25519_ephemeral_pk, self.kyber_sk, self.x25519_sk
            )
            
            print("[Worker] Unwrapping AES session key...")
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            kek_aesgcm = AESGCM(shared_secret[:32])
            session_key = kek_aesgcm.decrypt(kek_nonce, wrapped_session_key, None)
        except Exception as e:
            print(f"[Worker] FATAL: Failed to decapsulate session key from IPFS manifest: {e}")
            return b""
            
        aes_key = session_key[:32]
        
        # 2. Decrypt the Payload
        print("[Worker] Decrypting payload inside Enclave...")
        aesgcm = AESGCM(aes_key)
        try:
            decrypted_data = aesgcm.decrypt(nonce_bytes, ct_bytes, None)
            payload_script = decrypted_data.decode('utf-8')
        except Exception as e:
            print(f"[Worker] Decryption failed: {e}")
            return b""
            
        # 3. Write to temporary execution script
        enclave_script_path = "enclave_payload.py"
        with open(enclave_script_path, "w") as f:
            f.write(payload_script)
            
        # 4. Execute the payload in a sandboxed subprocess
        print(f"[Worker] Executing {enclave_script_path}...")
        try:
            # We use subprocess to simulate isolation
            result = subprocess.run(
                [sys.executable, enclave_script_path], 
                capture_output=True, 
                text=True,
                check=True
            )
            execution_output = result.stdout.strip()
            print(f"\n--- ENCLAVE EXECUTION OUTPUT ---\n{execution_output}\n--------------------------------\n")
        except subprocess.CalledProcessError as e:
            print(f"[Worker] Payload execution failed with error: {e.stderr}")
            execution_output = e.stderr.strip()
            
        # Clean up the script
        if os.path.exists(enclave_script_path):
            os.remove(enclave_script_path)
        
        # 5. Produce ZK-SNARK Proof from actual output
        proof_data = zk_prover.generate_groth16_proof(execution_output)
        print(f"Generated ZK Proof Public Input (Hash): {proof_data['raw_hash'].hex()}")
        
        # 6. Generate TEE Hardware Attestation Report (AMD SEV-SNP or Intel TDX)
        # We bind the result hash to the hardware report using the user_data/report_data field
        attestation_report = self.get_tee_attestation_report(proof_data["raw_hash"])
        if attestation_report:
            print(f"[Worker] Hardware Attestation Report generated successfully! Length: {len(attestation_report)} bytes")
            # In a full implementation, this report would be submitted on-chain or to an off-chain verifier
            # self.submit_attestation(job_id, attestation_report)
        
        return proof_data

    def get_tee_attestation_report(self, report_data: bytes) -> bytes:
        """
        Interacts with the TEE guest device driver to request a hardware attestation report.
        Supports both AMD SEV-SNP (/dev/sev-guest) and Intel TDX (/dev/tdx_guest) (e.g. AWS m7i).
        If no device is present, generates a mocked report for testing purposes.
        """
        import fcntl
        import ctypes
        import os
        
        SEV_GUEST_DEVICE = "/dev/sev-guest"
        TDX_GUEST_DEVICE = "/dev/tdx_guest"
        
        # Ensure report_data is exactly 64 bytes for TEE report binding
        if len(report_data) < 64:
            report_data = report_data + b'\x00' * (64 - len(report_data))
        elif len(report_data) > 64:
            report_data = report_data[:64]

        # Check for Intel TDX (AWS m7i / c7i)
        if os.path.exists(TDX_GUEST_DEVICE):
            print(f"[TEE] {TDX_GUEST_DEVICE} found. Requesting hardware attestation report from Intel TDX Module...")
            try:
                # TDX IOCTL definitions
                TDX_CMD_GET_REPORT0 = 0xc4405401
                
                class TdxReportReq(ctypes.Structure):
                    _pack_ = 1
                    _fields_ = [
                        ("reportdata", ctypes.c_uint8 * 64),
                        ("tdreport", ctypes.c_uint8 * 1024),
                    ]
                
                req = TdxReportReq()
                for i in range(64):
                    req.reportdata[i] = report_data[i]
                    
                with open(TDX_GUEST_DEVICE, "r+b") as f:
                    fcntl.ioctl(f.fileno(), TDX_CMD_GET_REPORT0, req)
                    
                return bytes(req.tdreport)
                
            except Exception as e:
                print(f"[TEE] Failed to get Intel TDX report via ioctl: {e}")
                print("[TEE] Ensure you are running on an Intel TDX-enabled instance and the driver is loaded.")

        # Check for AMD SEV-SNP
        elif os.path.exists(SEV_GUEST_DEVICE):
            print(f"[TEE] {SEV_GUEST_DEVICE} found. Requesting hardware attestation report from AMD Secure Processor...")
            try:
                # AMD SEV-SNP IOCTL structures and codes
                SNP_GET_REPORT = 0xc0185300
                
                class SnpReportReq(ctypes.Structure):
                    _pack_ = 1
                    _fields_ = [
                        ("user_data", ctypes.c_uint8 * 64),
                        ("vmpl", ctypes.c_uint32),
                        ("rsvd", ctypes.c_uint8 * 28),
                    ]

                class SnpReportResp(ctypes.Structure):
                    _pack_ = 1
                    _fields_ = [
                        ("data", ctypes.c_uint8 * 4000),
                    ]

                class SnpGuestRequestIoctl(ctypes.Structure):
                    _pack_ = 1
                    _fields_ = [
                        ("msg_version", ctypes.c_uint8),
                        ("req_data", ctypes.c_uint64),
                        ("resp_data", ctypes.c_uint64),
                        ("error_code", ctypes.c_uint64),
                    ]

                req = SnpReportReq()
                for i in range(64):
                    req.user_data[i] = report_data[i]
                req.vmpl = 0
                
                resp = SnpReportResp()
                
                ioctl_req = SnpGuestRequestIoctl()
                ioctl_req.msg_version = 1
                ioctl_req.req_data = ctypes.addressof(req)
                ioctl_req.resp_data = ctypes.addressof(resp)
                ioctl_req.error_code = 0
                
                with open(SEV_GUEST_DEVICE, "r+b") as f:
                    fcntl.ioctl(f.fileno(), SNP_GET_REPORT, ioctl_req)
                    
                # Extract the 1184 byte report from the response payload
                report_bytes = bytes(resp.data[:1184])
                print("[TEE] Cryptographically bound execution result to SEV-SNP Attestation Report.")
                return report_bytes
                
            except Exception as e:
                print(f"[TEE] Failed to get SEV-SNP report via ioctl: {e}")
                print("[TEE] Ensure your kernel has the sev-guest driver loaded and permissions are correct.")

        # Fallback for local testing (No TEE)
        print("[TEE] Neither /dev/sev-guest nor /dev/tdx_guest found. Running in non-confidential mode.")
        print("[TEE] Generating mocked Intel TDX attestation report (1024 bytes)...")
        # Generate a fake 1024 byte report containing the bound report_data
        return b"MOCK_TDX_REPORT_" + report_data + (b'\x00' * (1024 - 16 - 64))

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
                    if state == 3: # KeyProvided
                        job_info = self.contract.functions.getJob(job_id).call()
                        assigned_worker = job_info[7]
                        
                        if assigned_worker == self.account.address:
                            print(f"\n[Worker] Key Provided for Job {job_id}!")
                            cid = job_info[2]
                            encrypted_session_key_hex = job_info[8]
                            self.mark_executing(job_id)
                            proof_hash = self.simulate_execution(job_id, cid, encrypted_session_key_hex)
                            self.submit_proof(job_id, proof_hash)
                            
                            # Release the locked stake back to our wallet
                            self.reclaim_stake(job_id)
                            
                            processed_jobs.remove(job_id) # Done
                        else:
                            print(f"\n[Worker] Job {job_id} assigned to a different worker.")
                            processed_jobs.remove(job_id) # We lost the bid
                except Exception:
                    pass
                    
            time.sleep(3)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("Starting Confidential Worker Node...")
    
    PROVIDER_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
    
    # Account #1 from Hardhat local node (Worker identity)
    PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    abi_path = os.path.join(
        project_root, 
        "contracts", "artifacts", "contracts", "JobOrchestrator.sol", "JobOrchestrator.json"
    )
    
    contract_address = os.getenv("JOB_ORCHESTRATOR_ADDRESS")
    if not contract_address:
        address_path = os.path.join(project_root, "contracts", "deployed_addresses.json")
        if not os.path.exists(address_path):
            print(f"Error: Deployed addresses not found at {address_path} and JOB_ORCHESTRATOR_ADDRESS not set in .env")
            print("Please deploy the contracts first by running `npx hardhat run scripts/deploy.ts --network localhost` inside the 'contracts' directory.")
            sys.exit(1)
            
        with open(address_path, 'r') as f:
            addresses = json.load(f)
            contract_address = addresses.get("JobOrchestrator")
    
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
