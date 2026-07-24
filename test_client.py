import subprocess
import json

def test_pqc_connection():
    print("Testing connection to PQC API Gateway...")
    
    # We use the openquantumsafe/curl image because it has Kyber built-in.
    # Normally on a system with standard curl, it would fall back to classical X25519 if it doesn't support Kyber.
    # But since we enforced x25519_kyber768 on the server, a classical client will fail to connect.
    # Therefore, we use a PQC-enabled curl client.
    
    command = [
        "docker", "run", "--rm", "--network", "vtproject2_default",
        "openquantumsafe/curl", "curl", "-k", "-v", "https://vtproject2-nginx-pqc-1:4433"
    ]
    
    try:
        # Run curl and capture output (both stdout and stderr, since -v writes to stderr)
        result = subprocess.run(command, capture_output=True, text=True)
        
        # We want to parse the stderr to see what curve was negotiated
        stderr = result.stderr
        
        curve_negotiated = "kyber" in stderr.lower() or "mlkem" in stderr.lower()
        
        print("\n--- Connection Results ---")
        print("STDERR: ", stderr)
        if curve_negotiated:
            print("[SUCCESS] The connection successfully negotiated a Post-Quantum curve!")
        else:
            print("[WARNING] The connection did not negotiate the expected Post-Quantum curve.")
            print("Check the full logs below for details.")
            
        print("\n--- Server Response ---")
        print(result.stdout)
        
        print("\n--- TLS Handshake Details (Snippet) ---")
        # Extract just the lines showing the negotiated cipher and curve
        for line in stderr.split('\n'):
            if "SSL connection using" in line or "Server public key is" in line or "kyber" in line.lower():
                print(line.strip())
                
    except Exception as e:
        print(f"Failed to run the test: {e}")

if __name__ == "__main__":
    test_pqc_connection()
