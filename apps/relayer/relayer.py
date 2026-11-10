import os
import json
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(override=True)

# Connect to Node (Default to localhost, configurable via RPC_URL)
RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# The default hardhat private key for Account 0 (which we set as relayer)
RELAYER_PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
RELAYER_ADDRESS = w3.eth.account.from_key(RELAYER_PRIVATE_KEY).address

# Load Addresses
client_gateway_addr = os.getenv("CLIENT_GATEWAY_ADDRESS")
orchestrator_addr = os.getenv("JOB_ORCHESTRATOR_ADDRESS")

if not client_gateway_addr or not orchestrator_addr:
    addresses_path = os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "deployed_addresses.json")
    if os.path.exists(addresses_path):
        with open(addresses_path, "r") as f:
            addresses = json.load(f)
            client_gateway_addr = addresses.get("ClientGateway")
            orchestrator_addr = addresses.get("JobOrchestrator")

if not client_gateway_addr or not orchestrator_addr:
    print("Error: Contract addresses not provided in .env or deployed_addresses.json")
    exit(1)

# ABI paths
client_gateway_abi_path = os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "artifacts", "contracts", "ClientGateway.sol", "ClientGateway.json")
orchestrator_abi_path = os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "artifacts", "contracts", "JobOrchestrator.sol", "JobOrchestrator.json")

with open(client_gateway_abi_path, "r") as f:
    client_gateway_abi = json.load(f)["abi"]

with open(orchestrator_abi_path, "r") as f:
    orchestrator_abi = json.load(f)["abi"]

client_gateway = w3.eth.contract(address=client_gateway_addr, abi=client_gateway_abi)
orchestrator = w3.eth.contract(address=orchestrator_addr, abi=orchestrator_abi)

print(f"Starting Cross-Chain Relayer as {RELAYER_ADDRESS}...")
print(f"Listening to ClientGateway ({client_gateway.address}) and JobOrchestrator ({orchestrator.address})...")

def process_funded_events(last_block):
    current_block = w3.eth.block_number
    if current_block < last_block:
        return current_block

    try:
        events = client_gateway.events.CrossChainJobFunded.get_logs(from_block=last_block, to_block=current_block)
    except Exception:
        events = client_gateway.events.CrossChainJobFunded.create_filter(from_block=last_block, to_block=current_block).get_all_entries()
    for event in events:
        args = event['args']
        print(f"\n[Relayer] Detected CrossChainJobFunded! JobID: {args['jobId']}, Budget: {args['budget']}")
        print(f"[Relayer] Relaying to JobOrchestrator (Logical Chain B)...")
        
        tx = orchestrator.functions.receiveCrossChainJob(
            args['jobId'],
            args['client'],
            args['budget'],
            args['cid'],
            args['minCpu'],
            args['minGpuVram'],
            args['minRam']
        ).build_transaction({
            'from': RELAYER_ADDRESS,
            'nonce': w3.eth.get_transaction_count(RELAYER_ADDRESS),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"[Relayer] Job {args['jobId']} successfully bridged to Chain B!")

    return current_block + 1

def process_completed_events(last_block):
    current_block = w3.eth.block_number
    if current_block < last_block:
        return current_block

    try:
        events = orchestrator.events.CrossChainJobCompleted.get_logs(from_block=last_block, to_block=current_block)
    except Exception:
        events = orchestrator.events.CrossChainJobCompleted.create_filter(from_block=last_block, to_block=current_block).get_all_entries()
    for event in events:
        args = event['args']
        print(f"\n[Relayer] Detected CrossChainJobCompleted! JobID: {args['jobId']}, Worker: {args['worker']}")
        print(f"[Relayer] Triggering escrow payout on ClientGateway (Logical Chain A)...")
        
        tx = client_gateway.functions.releasePayment(
            args['jobId'],
            args['worker']
        ).build_transaction({
            'from': RELAYER_ADDRESS,
            'nonce': w3.eth.get_transaction_count(RELAYER_ADDRESS),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=RELAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"[Relayer] Payment released to Worker {args['worker']} on Chain A!")

    return current_block + 1

last_block_a = w3.eth.block_number
last_block_b = w3.eth.block_number

while True:
    try:
        last_block_a = process_funded_events(last_block_a)
        last_block_b = process_completed_events(last_block_b)
    except Exception as e:
        print(f"[Error] {e}")
    time.sleep(2)
