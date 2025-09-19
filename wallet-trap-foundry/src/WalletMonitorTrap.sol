
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ITrap {
    function collect() external view returns (bytes memory);
    function analyze(bytes calldata data) external view returns (bool, bytes memory);
}

contract WalletMonitorTrap is ITrap {
    address public monitoredWallet;
    address public safeVault;
    uint256 public lastNonce;
    uint256 public thresholdValue;
    mapping(address => bool) public approvedSigners;

    constructor(address _wallet, address _vault, uint256 _threshold) {
        monitoredWallet = _wallet;
        safeVault = _vault;
        thresholdValue = _threshold;
        approvedSigners[msg.sender] = true;
    }

    // Collect function no longer tries to access nonce directly
    function collect() external view override returns (bytes memory) {
        uint256 balance = monitoredWallet.balance;
        return abi.encode(lastNonce, balance, block.timestamp);
    }

    function analyze(bytes calldata data) external view override returns (bool, bytes memory) {
        (uint256 currentNonce, uint256 balance, uint256 timestamp) = abi.decode(data, (uint256, uint256, uint256));
        
        // Only trigger if the nonce has increased and balance is below threshold
        if (currentNonce > lastNonce) {
            if (balance < thresholdValue) {
                bytes memory responseData = abi.encodeWithSignature("transfer(address,uint256)", safeVault, balance);
                return (true, responseData);
            }
        }
        return (false, "");
    }

    // Function to manually update the nonce
    function updateNonce(uint256 newNonce) external {
        lastNonce = newNonce;
    }

    // Add signer function, keeping it as is
    function addSigner(address signer) external {
        require(approvedSigners[msg.sender], "Not authorized");
        approvedSigners[signer] = true;
    }
}
