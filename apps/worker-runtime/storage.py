import requests
import json

IPFS_API_URL = "http://127.0.0.1:5001/api/v0"
IPFS_GATEWAY_URL = "http://127.0.0.1:8080/ipfs"

class StorageClient:
    def upload_dict(self, data: dict) -> str:
        """Uploads a dictionary to IPFS and returns the CID."""
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
            # Try IPFS API cat
            response = requests.post(f"{IPFS_API_URL}/cat?arg={cid}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            # Fallback to Gateway
            response = requests.get(f"{IPFS_GATEWAY_URL}/{cid}")
            response.raise_for_status()
            return response.json()
