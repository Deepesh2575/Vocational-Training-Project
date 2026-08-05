import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Fallback Local IPFS
IPFS_API_URL = "http://127.0.0.1:5001/api/v0"
IPFS_GATEWAY_URL = "http://127.0.0.1:8080/ipfs"

# Pinata API
PINATA_API_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
PINATA_GATEWAY_URL = "https://gateway.pinata.cloud/ipfs"

class StorageClient:
    def __init__(self):
        # Prefer environment variables if loaded (e.g. from a .env file)
        self.pinata_api_key = os.getenv("PINATA_API_KEY")
        self.pinata_secret = os.getenv("PINATA_SECRET_API_KEY")

    def upload_dict(self, data: dict) -> str:
        """Uploads a dictionary to IPFS and returns the CID."""
        if self.pinata_api_key and self.pinata_secret:
            print("[IPFS Client] Uploading to Pinata...")
            headers = {
                "pinata_api_key": self.pinata_api_key,
                "pinata_secret_api_key": self.pinata_secret,
            }
            payload = {
                "pinataOptions": {"cidVersion": 1},
                "pinataMetadata": {"name": "client_payload"},
                "pinataContent": data
            }
            response = requests.post(PINATA_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result['IpfsHash']
        else:
            print("[IPFS Client] Uploading to Local Daemon (No Pinata keys found)...")
            files = {
                'file': ('manifest.json', json.dumps(data))
            }
            response = requests.post(f"{IPFS_API_URL}/add", files=files)
            response.raise_for_status()
            result = response.json()
            return result['Hash']

    def download_dict(self, cid: str) -> dict:
        """Downloads a JSON file from IPFS given a CID."""
        if cid.startswith("ipfs://"):
            cid = cid.replace("ipfs://", "")
            
        try:
            if self.pinata_api_key:
                # Try Pinata Gateway
                response = requests.get(f"{PINATA_GATEWAY_URL}/{cid}")
                response.raise_for_status()
                return response.json()
            else:
                # Try IPFS API cat
                response = requests.post(f"{IPFS_API_URL}/cat?arg={cid}")
                response.raise_for_status()
                return response.json()
        except requests.exceptions.RequestException:
            # Fallback to public Gateway
            public_gw = f"https://ipfs.io/ipfs/{cid}"
            print(f"[IPFS Client] Fallback: Fetching from {public_gw}")
            response = requests.get(public_gw)
            response.raise_for_status()
            return response.json()
