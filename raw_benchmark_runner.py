import time
import statistics
import os
import crypto_pqc
import tenseal as ts
import hashlib

def run_benchmarks(iterations=50):
    print("="*60)
    print("RUNNING RAW CRYPTOGRAPHIC AND FHE BENCHMARKS")
    print(f"Iterations per primitive: {iterations}")
    print("="*60)
    
    # 1. PQC Hybrid Keygen
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        k_pk, k_sk, x_pk, x_sk = crypto_pqc.generate_hybrid_keypair()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"Hybrid Keygen (ML-KEM-768 + X25519): Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")

    # 2. PQC Hybrid Encapsulation
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        ct, epk, ss = crypto_pqc.client_encapsulate(k_pk, x_pk)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"Hybrid Encapsulation (Client):       Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")

    # 3. PQC Hybrid Decapsulation
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        worker_ss = crypto_pqc.worker_decapsulate(ct, epk, k_sk, x_sk)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"Hybrid Decapsulation (Worker):       Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    assert ss == worker_ss, "Shared secrets do not match!"

    # 4. ML-DSA-65 Keygen
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        mldsa_vk, mldsa_sk = crypto_pqc.generate_mldsa_keys()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"ML-DSA-65 Keygen (FIPS 204):         Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")

    # 5. ML-DSA-65 Sign
    msg = b"Decentralized Compute Payload Provenance Manifest Hash: " + os.urandom(32)
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        sig = crypto_pqc.sign_message(mldsa_sk, msg)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"ML-DSA-65 Sign (FIPS 204):           Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")

    # 6. ML-DSA-65 Verify
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        val = crypto_pqc.verify_signature(mldsa_vk, msg, sig)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"ML-DSA-65 Verify (FIPS 204):         Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")

    # 7. TenSEAL CKKS Vector Encrypt
    context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=8192, coeff_mod_bit_sizes=[60, 40, 40, 60])
    context.generate_galois_keys()
    context.global_scale = 2**40
    raw_vector = [10.5, 20.5, 30.5, 40.5]
    
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        enc_v = ts.ckks_vector(context, raw_vector)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"TenSEAL CKKS Encrypt (4 slots):      Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")

    # 8. TenSEAL CKKS Homomorphic Eval (x*x + 10)
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        res_v = enc_v * enc_v + 10
        times.append((time.perf_counter() - t0) * 1000)
    print(f"TenSEAL CKKS Homomorphic Eval:       Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")

    # 9. TenSEAL CKKS Decrypt
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        dec_v = res_v.decrypt()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"TenSEAL CKKS Decrypt:                Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    print("="*60)

if __name__ == "__main__":
    run_benchmarks(50)

