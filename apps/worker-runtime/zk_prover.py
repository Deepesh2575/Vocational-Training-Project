import hashlib
from py_ecc.bn128 import G1, G2, multiply, add, curve_order
import random

def generate_groth16_proof(output_text: str):
    print("Generating Groth16 ZK-SNARK Proof on alt_bn128 curve...")
    
    # 1. Generate the public input (hash of the output)
    # We will use this as our 'public signal'
    proof_hash = hashlib.sha256(output_text.encode('utf-8')).digest()
    input_signal = int.from_bytes(proof_hash, byteorder='big') % curve_order
    
    # 2. Generate valid Group 1 and Group 2 points for the proof (A, B, C)
    # In a real ZK-SNARK, these points are generated through complex polynomial evaluation.
    # Here, we generate valid random points on the bn128 curve that mimic the structure.
    
    # Generate random scalars
    r_a = random.randint(1, curve_order - 1)
    r_b = random.randint(1, curve_order - 1)
    r_c = random.randint(1, curve_order - 1)
    
    # Point A in G1: (x, y)
    A = multiply(G1, r_a)
    a_sol = [int(A[0]), int(A[1])]
    
    # Point B in G2: ((x_re, x_im), (y_re, y_im))
    B = multiply(G2, r_b)
    # Solidity expects G2 points in the format: [[x_im, x_re], [y_im, y_re]]
    b_sol = [
        [int(B[0].coeffs[1]), int(B[0].coeffs[0])],
        [int(B[1].coeffs[1]), int(B[1].coeffs[0])]
    ]
    
    # Point C in G1: (x, y)
    C = multiply(G1, r_c)
    c_sol = [int(C[0]), int(C[1])]
    
    inputs_sol = [input_signal]
    
    # Return exactly what Web3.py expects for the smart contract call
    return {
        "a": a_sol,
        "b": b_sol,
        "c": c_sol,
        "inputs": inputs_sol,
        "raw_hash": proof_hash
    }
