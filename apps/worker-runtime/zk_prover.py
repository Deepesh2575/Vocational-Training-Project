import hashlib
import json
import os
import subprocess

def generate_groth16_proof(output_text: str):
    print("Generating REAL Groth16 ZK-SNARK Proof via SnarkJS...")
    
    # We use a dummy Multiplier2 circuit for demonstration of a real Groth16 pipeline.
    # In a true zkVM, the circuit would verify the execution trace.
    # Here we just prove we know two factors that multiply to our 'public signal'.
    # We'll use a = hash(output), b = 1.
    
    proof_hash = hashlib.sha256(output_text.encode('utf-8')).digest()
    
    # alt_bn128 curve order
    curve_order = 21888242871839275222246405745257275088696311157297823662689037894645226208583
    input_signal = int.from_bytes(proof_hash, byteorder='big') % curve_order
    
    circuit_dir = os.path.join(os.path.dirname(__file__), "circuits")
    input_path = os.path.join(circuit_dir, "input.json")
    
    with open(input_path, "w") as f:
        json.dump({"a": str(input_signal), "b": "1"}, f)
        
    wasm_path = os.path.join(circuit_dir, "multiplier_js", "multiplier.wasm")
    wtns_js = os.path.join(circuit_dir, "multiplier_js", "generate_witness.js")
    zkey_path = os.path.join(circuit_dir, "multiplier_final.zkey")
    wtns_path = os.path.join(circuit_dir, "witness.wtns")
    proof_path = os.path.join(circuit_dir, "proof.json")
    public_path = os.path.join(circuit_dir, "public.json")
    
    # Check if circuit is built
    if not os.path.exists(zkey_path):
        raise FileNotFoundError(f"Circuit artifacts not found at {circuit_dir}. Please run build_circuit.ps1 first.")
    
    # 1. Generate witness
    print("[ZK] Generating witness...")
    subprocess.run(["node", wtns_js, wasm_path, input_path, wtns_path], check=True)
    
    # 2. Generate proof
    print("[ZK] Generating proof...")
    subprocess.run(["snarkjs", "groth16", "prove", zkey_path, wtns_path, proof_path, public_path], check=True, shell=True)
    
    # 3. Parse proof for Solidity
    with open(proof_path, "r") as f:
        proof = json.load(f)
        
    with open(public_path, "r") as f:
        public_signals = json.load(f)
        
    # Format for Solidity (web3.py expects integers)
    a_sol = [int(proof["pi_a"][0]), int(proof["pi_a"][1])]
    # Note: SnarkJS outputs G2 points in [x, y] where each is [real, imag] or vice versa.
    # Solidity expects [[x_imag, x_real], [y_imag, y_real]] usually, let's format it standard:
    b_sol = [
        [int(proof["pi_b"][0][1]), int(proof["pi_b"][0][0])],
        [int(proof["pi_b"][1][1]), int(proof["pi_b"][1][0])]
    ]
    c_sol = [int(proof["pi_c"][0]), int(proof["pi_c"][1])]
    inputs_sol = [int(sig) for sig in public_signals]
    
    return {
        "a": a_sol,
        "b": b_sol,
        "c": c_sol,
        "inputs": inputs_sol,
        "raw_hash": int(inputs_sol[0]).to_bytes(32, byteorder='big')
    }
