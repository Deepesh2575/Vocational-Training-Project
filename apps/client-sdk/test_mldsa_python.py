import crypto_pqc
import os

def test_mldsa():
    print("Testing ML-DSA Python bindings...")
    vk, sk = crypto_pqc.generate_mldsa_keys()
    print(f"Generated Keys! VK length: {len(vk)}, SK length: {len(sk)}")
    
    message = b"Decentralized Compute Payload Provenance"
    print(f"Message to sign: {message}")
    
    signature = crypto_pqc.sign_message(sk, message)
    print(f"Signature length: {len(signature)}")
    
    is_valid = crypto_pqc.verify_signature(vk, message, signature)
    print(f"Signature valid? {is_valid}")
    
    assert is_valid, "Signature verification failed!"
    print("Success!")

if __name__ == "__main__":
    test_mldsa()
