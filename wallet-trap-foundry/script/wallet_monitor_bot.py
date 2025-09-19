import os
import time
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

HOODI_RPC_WS = 'wss://rpc.ankr.com/eth_hoodi/ws'
HOODI_RPC_HTTP = 'https://rpc.ankr.com/eth_hoodi/cd6e324ca8dc060988962797ba95215e35c69940c866afebd6984a903b047649'
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
TRAP_CONTRACT_ADDRESS = os.getenv('TRAP_CONTRACT_ADDRESS')  # From deployment
MONITORED_WALLET = Account.from_key(PRIVATE_KEY).address

TRAP_ABI = [  # From forge build output or compiled JSON
    {
        "inputs": [{"internalType": "address", "name": "_wallet", "type": "address"},
                   {"internalType": "address", "name": "_vault", "type": "address"},
                   {"internalType": "uint256", "name": "_threshold", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [{"internalType": "bytes", "name": "data", "type": "bytes"}],
        "name": "analyze",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"},
                    {"internalType": "bytes", "name": "", "type": "bytes"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "signer", "type": "address"}],
        "name": "addSigner",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "approvedSigners",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "collect",
        "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "lastNonce",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "monitoredWallet",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "safeVault",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "thresholdValue",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "updateNonce",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

w3 = Web3(Web3.WebsocketProvider(HOODI_RPC_WS))
if not w3.is_connected():
    print("WS not connected, falling back to HTTP")
    w3 = Web3(Web3.HTTPProvider(HOODI_RPC_HTTP))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

account = Account.from_key(PRIVATE_KEY)
trap_contract = w3.eth.contract(address=TRAP_CONTRACT_ADDRESS, abi=TRAP_ABI)

def trap_funds(tx_hash):
    try:
        collect_data = trap_contract.functions.collect().call()
        print(f"Collected data: {collect_data}")

        should_respond, response_data = trap_contract.functions.analyze(collect_data).call()
        if should_respond:
            print(f"Trap triggered! Response data: {response_data}")
            nonce = w3.eth.get_transaction_count(MONITORED_WALLET, 'pending')
            balance = w3.eth.get_balance(MONITORED_WALLET)
            tx = {
                'to': trap_contract.functions.safeVault().call(),
                'value': balance - w3.to_wei(0.001, 'ether'),
                'gas': 21000,
                'gasPrice': w3.eth.gas_price * 2,
                'nonce': nonce,
                'chainId': w3.eth.chain_id,
                'data': response_data if response_data else b''
            }
            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"Trapped funds tx: {tx_hash.hex()}")
        else:
            print("No trap needed")
    except Exception as e:
        print(f"Trap error: {e}")

def start_monitoring():
    print(f"Monitoring wallet: {MONITORED_WALLET} on Hoodi")
    initial_nonce = w3.eth.get_transaction_count(MONITORED_WALLET)
    trap_contract.functions.updateNonce().transact({'from': MONITORED_WALLET})

    try:
        pending_filter = w3.eth.filter('pending')
        while True:
            for tx_hash in pending_filter.get_new_entries():
                try:
                    tx = w3.eth.get_transaction(tx_hash)
                    if tx and tx['from'].lower() == MONITORED_WALLET.lower():
                        print(f"Detected outgoing tx: {tx_hash.hex()}")
                        trap_funds(tx_hash)
                except Exception as e:
                    print(f"Tx fetch error: {e}")
            time.sleep(1)
    except Exception as e:
        print(f"Monitoring error: {e}")
        last_nonce = initial_nonce
        while True:
            current_nonce = w3.eth.get_transaction_count(MONITORED_WALLET, 'pending')
            if current_nonce > last_nonce:
                print("Nonce increase detected - potential outgoing tx")
                trap_funds(None)
                last_nonce = current_nonce
            time.sleep(5)

if __name__ == "__main__":
    start_monitoring()