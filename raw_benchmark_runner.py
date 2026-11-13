import time
import statistics
import os
import sys
import platform
import subprocess
import shutil
import json
import tempfile
import hashlib
import crypto_pqc
import tenseal as ts

def run_benchmarks(iterations=50):
    print("="*75)
    print("SYSTEM AND ENVIRONMENT SPECIFICATION")
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Processor: {platform.processor()}")
    print(f"Python Version: {platform.python_version()}")
    print(f"TenSEAL Version: {ts.__version__}")
    print("="*75)
    print("RUNNING RAW CRYPTOGRAPHIC, FHE, AND GROTH16 ZK-SNARK BENCHMARKS")
    print(f"Iterations per primitive: {iterations}")
    print("="*75)
    
    results = {}

    # 1. PQC Hybrid Keygen
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        k_pk, k_sk, x_pk, x_sk = crypto_pqc.generate_hybrid_keypair()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"Hybrid Keygen (ML-KEM-768 + X25519): Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    results["hybrid_keygen"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 2. PQC Hybrid Encapsulation
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        ct, epk, ss = crypto_pqc.client_encapsulate(k_pk, x_pk)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"Hybrid Encapsulation (Client):       Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    results["hybrid_encaps"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 3. PQC Hybrid Decapsulation
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        worker_ss = crypto_pqc.worker_decapsulate(ct, epk, k_sk, x_sk)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"Hybrid Decapsulation (Worker):       Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    assert ss == worker_ss, "Shared secrets do not match!"
    results["hybrid_decaps"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 4. ML-DSA-65 Keygen
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        mldsa_vk, mldsa_sk = crypto_pqc.generate_mldsa_keys()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"ML-DSA-65 Keygen (FIPS 204):         Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    results["mldsa_keygen"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 5. ML-DSA-65 Sign
    msg = b"Decentralized Compute Payload Provenance Manifest Hash: " + os.urandom(32)
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        sig = crypto_pqc.sign_message(mldsa_sk, msg)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"ML-DSA-65 Sign (FIPS 204):           Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    results["mldsa_sign"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 6. ML-DSA-65 Verify
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        val = crypto_pqc.verify_signature(mldsa_vk, msg, sig)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"ML-DSA-65 Verify (FIPS 204):         Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    results["mldsa_verify"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

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
    results["ckks_encrypt"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 8. TenSEAL CKKS Homomorphic Eval (x*x + 10)
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        res_v = enc_v * enc_v + 10
        times.append((time.perf_counter() - t0) * 1000)
    print(f"TenSEAL CKKS Homomorphic Eval:       Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    results["ckks_eval"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 9. TenSEAL CKKS Decrypt
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        dec_v = res_v.decrypt()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"TenSEAL CKKS Decrypt:                Mean = {statistics.mean(times):.4f} ms, Std = {statistics.stdev(times):.4f} ms, Min = {min(times):.4f} ms, Max = {max(times):.4f} ms")
    results["ckks_decrypt"] = (statistics.mean(times), statistics.stdev(times), min(times), max(times))

    # 10. Groth16 ComputeRelation Prover & Verifier Benchmark
    circuits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps", "worker-runtime", "circuits")
    wasm_path = os.path.join(circuits_dir, "compute_relation_js", "compute_relation.wasm")
    zkey_path = os.path.join(circuits_dir, "compute_relation_final.zkey")
    vkey_path = os.path.join(circuits_dir, "verification_key.json")

    if os.path.exists(wasm_path) and os.path.exists(zkey_path) and os.path.exists(vkey_path):
        snarkjs_bin = shutil.which("snarkjs")
        npx_bin = shutil.which("npx")
        shell_needed = (sys.platform == "win32") and not snarkjs_bin
        cmd_prefix = [snarkjs_bin] if snarkjs_bin else [npx_bin, "snarkjs"]

        # Run 10 iterations for ZK proving (heavier computation)
        zk_iters = min(15, iterations)
        prove_times = []
        verify_times = []

        with tempfile.TemporaryDirectory() as tmpdir:
            input_json = os.path.join(tmpdir, "input.json")
            proof_json = os.path.join(tmpdir, "proof.json")
            public_json = os.path.join(tmpdir, "public.json")
            with open(input_json, "w") as f:
                json.dump({"x": "42", "r": "987654321"}, f)

            for _ in range(zk_iters):
                t0 = time.perf_counter()
                subprocess.run(cmd_prefix + ["groth16", "fullprove", input_json, wasm_path, zkey_path, proof_json, public_json],
                               capture_output=True, text=True, shell=shell_needed, check=True)
                prove_times.append((time.perf_counter() - t0) * 1000)

                t0 = time.perf_counter()
                subprocess.run(cmd_prefix + ["groth16", "verify", vkey_path, public_json, proof_json],
                               capture_output=True, text=True, shell=shell_needed, check=True)
                verify_times.append((time.perf_counter() - t0) * 1000)

        print(f"Groth16 Prover (ComputeRelation):    Mean = {statistics.mean(prove_times):.4f} ms, Std = {statistics.stdev(prove_times):.4f} ms, Min = {min(prove_times):.4f} ms, Max = {max(prove_times):.4f} ms")
        print(f"Groth16 Local Verifier:              Mean = {statistics.mean(verify_times):.4f} ms, Std = {statistics.stdev(verify_times):.4f} ms, Min = {min(verify_times):.4f} ms, Max = {max(verify_times):.4f} ms")
        results["groth16_prove"] = (statistics.mean(prove_times), statistics.stdev(prove_times), min(prove_times), max(prove_times))
        results["groth16_verify"] = (statistics.mean(verify_times), statistics.stdev(verify_times), min(verify_times), max(verify_times))

    print("="*75)
    return results

if __name__ == "__main__":
    run_benchmarks(50)
