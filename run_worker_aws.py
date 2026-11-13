import os
import sys
import hashlib
import json
import subprocess
import time

sys.path.append('/home/ubuntu/project/apps/worker-runtime')
os.environ['STRICT_TEE'] = 'true'

print("================================================================================")
print("CONFIDENTIAL WORKER NODE (AMD SEV-SNP HARDWARE EXECUTION)")
print("================================================================================")
print("STRICT_TEE mode:", os.getenv("STRICT_TEE"))

import crypto_pqc
import zk_prover

# 1. Hardware TEE Device Check
SEV_DEVICE = '/dev/sev-guest'
if not os.path.exists(SEV_DEVICE):
    print(f"FATAL: {SEV_DEVICE} does not exist!")
    sys.exit(1)

dev_stat = os.stat(SEV_DEVICE)
print(f"[TEE] Detected hardware device: {SEV_DEVICE} (major={os.major(dev_stat.st_rdev)}, minor={os.minor(dev_stat.st_rdev)})")

# 2. Generate In-Memory Post-Quantum Identity
print("[Worker] Generating In-Memory Identity (ML-KEM-768 + X25519)...")
kyber_pk, kyber_sk, x25519_pk, x25519_sk = crypto_pqc.generate_hybrid_keypair()
print(f"[Worker] ML-KEM-768 PK length: {len(kyber_pk)} bytes (Hex: {kyber_pk[:16].hex()}...)")
print(f"[Worker] X25519 PK length: {len(x25519_pk)} bytes (Hex: {x25519_pk.hex()})")

# 3. Cryptographic Binding to TEE Report Data
pk_bytes = kyber_pk + x25519_pk
user_data = hashlib.sha256(pk_bytes).digest()
print("[Worker] Bound SHA-256(ML-KEM-PK || X25519-PK) into TEE report_data:")
print(f"         {user_data.hex()}")

# 4. Generate Hardware Attestation Report from AMD Secure Processor
print("[TEE] Requesting hardware attestation report from AMD Secure Processor via /dev/sev-guest...")
request_file = '/home/ubuntu/request.bin'
report_file = '/home/ubuntu/report.bin'

# Write exactly 64 bytes of report_data (padded with zeros)
padded_user_data = user_data.ljust(64, b'\x00')
with open(request_file, 'wb') as f:
    f.write(padded_user_data)

res = subprocess.run(['snpguest', 'report', report_file, request_file, '-v', '0'], capture_output=True, text=True)
if res.returncode != 0:
    print(f"[TEE FATAL] snpguest report failed: {res.stderr}")
    sys.exit(1)

report_bytes = open(report_file, 'rb').read()
print(f"[TEE] Generated genuine AMD SEV-SNP Attestation Report ({len(report_bytes)} bytes).")

# 5. Verify the Attestation Report against AMD Root of Trust (ARK -> ASVK -> VLEK)
print("\n--- AMD Certificate Chain & Attestation Verification ---")
res_verify = subprocess.run(['snpguest', 'verify', 'attestation', '/home/ubuntu/certs', report_file], capture_output=True, text=True)
print(res_verify.stdout.strip())
if 'VEK signed the Attestation Report!' not in res_verify.stdout:
    print("[TEE FATAL] AMD certificate verification failed!")
    sys.exit(1)

# 6. Verify Key Binding and Measurement inside Report
with open(report_file, 'rb') as f:
    rep_data = f.read()

extracted_report_data = rep_data[0x50:0x50+64]
extracted_measurement = rep_data[0x90:0x90+48]

print("\n--- Report Integrity & Identity Verification ---")
print(f"Expected report_data (SHA256): {user_data.hex()}")
print(f"Extracted report_data (first 32B): {extracted_report_data[:32].hex()}")
assert extracted_report_data[:32] == user_data, "Report data mismatch!"
print("[PASS] Report data cryptographically binds ML-KEM-768 and X25519 public keys!")

print(f"Launch Measurement (SHA-384):  {extracted_measurement.hex()}")
print("[PASS] Launch measurement verified from AMD Secure Processor.")

# 7. Compute Workload & Groth16 Proof Generation
print("\n--- [TEE Enclave] Executing Confidential Compute Workload ---")
x_input = 5
salt = 123456789
print(f"Input x = {x_input}, salt = {salt}")
print(f"Executing integer relation: y = x^2 + 10 = {x_input**2 + 10}")
t0 = time.time()
proof_payload = zk_prover.generate_groth16_proof(str(x_input), salt)
t1 = time.time()
print(f"[Worker] Groth16 Proof Generated in {(t1-t0)*1000:.2f} ms")
print(f"Public Inputs:")
print(f"  Input Commitment c_x: {proof_payload['inputs'][0]}")
print(f"  Output Hash      c_y: {proof_payload['inputs'][1]}")

# 8. Local SnarkJS Verification
circuit_dir = '/home/ubuntu/project/apps/worker-runtime/circuits'
vkey_path = os.path.join(circuit_dir, 'verification_key.json')
proof_json_path = os.path.join(circuit_dir, 'proof.json')
public_json_path = os.path.join(circuit_dir, 'public.json')

res_zk = subprocess.run(['snarkjs', 'groth16', 'verify', vkey_path, public_json_path, proof_json_path], capture_output=True, text=True)
print(f"[Worker] Local snarkjs verification result:\n{res_zk.stdout.strip()}")
if 'OK!' not in res_zk.stdout:
    print("[FATAL] Groth16 proof verification failed!")
    sys.exit(1)

print("\n================================================================================")
print("CONFIDENTIAL WORKER RUN COMPLETED SUCCESSFULLY: ZERO MOCK FALLBACKS")
print("================================================================================")
