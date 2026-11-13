import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile

PRIME_Q = 21888242871839275222246405745257275088696311157297823662689037894645226208583
PRIME_R = 21888242871839275222246405745257275088548364400416034343698204186575808495617

def generate_groth16_proof(output_text: str = "42", salt: int = None):
    """
    Generates a production Groth16 ZK-SNARK proof for the ComputeRelation circuit:
      - Private input: x, private salt: r
      - Public output 0: c_x = Poseidon(x, r) (commitment to input)
      - Integer relation: y = x^2 + 10
      - Public output 1: c_y = Poseidon(y) (hash of output)
    """
    print("[ZK] Generating Groth16 ZK-SNARK Proof for ComputeRelation...")

    # Derive integer input x from payload text if string, or parse integer directly
    try:
        x_val = int(output_text) % PRIME_R
    except ValueError:
        # Hash non-numeric text to scalar field
        h = hashlib.sha256(output_text.encode('utf-8')).digest()
        x_val = int.from_bytes(h, byteorder='big') % PRIME_R

    # Blinding salt r
    if salt is None:
        r_val = secrets.randbelow(PRIME_R)
    else:
        r_val = int(salt) % PRIME_R

    worker_runtime_dir = os.path.dirname(os.path.abspath(__file__))
    circuits_dir = os.path.join(worker_runtime_dir, "circuits")

    wasm_path = os.path.join(circuits_dir, "compute_relation_js", "compute_relation.wasm")
    zkey_path = os.path.join(circuits_dir, "compute_relation_final.zkey")

    if not os.path.exists(wasm_path) or not os.path.exists(zkey_path):
        raise FileNotFoundError(
            f"[ZK FATAL] Missing circuit artifacts: {wasm_path} or {zkey_path}. "
            "Please compile compute_relation.circom and run snarkjs groth16 setup first."
        )

    print(f"[ZK] Using circuit wasm: {wasm_path}")
    print(f"[ZK] Using proving key: {zkey_path}")

    # Find snarkjs or npx executable
    snarkjs_bin = shutil.which("snarkjs")
    npx_bin = shutil.which("npx")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_json_path = os.path.join(tmpdir, "input.json")
        proof_json_path = os.path.join(tmpdir, "proof.json")
        public_json_path = os.path.join(tmpdir, "public.json")

        with open(input_json_path, "w") as f:
            json.dump({"x": str(x_val), "r": str(r_val)}, f)

        if snarkjs_bin:
            cmd = [snarkjs_bin, "groth16", "fullprove", input_json_path, wasm_path, zkey_path, proof_json_path, public_json_path]
            shell_needed = False
        elif npx_bin:
            cmd = [npx_bin, "snarkjs", "groth16", "fullprove", input_json_path, wasm_path, zkey_path, proof_json_path, public_json_path]
            shell_needed = (sys.platform == "win32")
        else:
            raise RuntimeError("[ZK FATAL] Neither snarkjs nor npx was found in PATH.")

        result = subprocess.run(cmd, capture_output=True, text=True, shell=shell_needed)
        if result.returncode != 0:
            raise RuntimeError(f"[ZK FATAL] snarkjs fullprove failed (code {result.returncode}):\n{result.stderr}\n{result.stdout}")

        with open(proof_json_path, "r") as f:
            proof = json.load(f)
        with open(public_json_path, "r") as f:
            public = json.load(f)

        # Persist proof.json and public.json in circuits directory for auditability
        try:
            with open(os.path.join(circuits_dir, "proof.json"), "w") as f:
                json.dump(proof, f, indent=2)
            with open(os.path.join(circuits_dir, "public.json"), "w") as f:
                json.dump(public, f, indent=2)
        except Exception:
            pass

        # Format points for Solidity alt_bn128 verifier (G1, G2, G1)
        a_sol = [int(proof["pi_a"][0]), int(proof["pi_a"][1])]
        b_sol = [
            [int(proof["pi_b"][0][1]), int(proof["pi_b"][0][0])],
            [int(proof["pi_b"][1][1]), int(proof["pi_b"][1][0])]
        ]
        c_sol = [int(proof["pi_c"][0]), int(proof["pi_c"][1])]
        inputs_sol = [int(public[0]), int(public[1])]

        c_x = inputs_sol[0]
        c_y = inputs_sol[1]
        raw_hash = c_y.to_bytes(32, byteorder='big')

        print(f"[ZK] SnarkJS proof successfully generated!")
        print(f"     Commitment c_x: {c_x}")
        print(f"     Output Hash c_y: {c_y}")
        print(f"     Raw Hash: {raw_hash.hex()}")

        return {
            "a": a_sol,
            "b": b_sol,
            "c": c_sol,
            "inputs": inputs_sol,
            "c_x": c_x,
            "c_y": c_y,
            "raw_hash": raw_hash
        }

if __name__ == "__main__":
    proof = generate_groth16_proof("5", salt=123456789)
    print("Proof test generated successfully.")
