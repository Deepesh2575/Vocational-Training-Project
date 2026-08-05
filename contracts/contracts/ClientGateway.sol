// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

contract ClientGateway is Ownable {
    address public relayer;
    uint256 public nextJobId;

    event CrossChainJobFunded(uint256 indexed jobId, address indexed client, uint256 budget, string cid, uint256 minCpu, uint256 minGpuVram, uint256 minRam);
    event JobPayoutReleased(uint256 indexed jobId, address indexed worker, uint256 amount);

    mapping(uint256 => uint256) public jobEscrows;

    modifier onlyRelayer() {
        require(msg.sender == relayer, "Only relayer can call this");
        _;
    }

    constructor(address initialOwner) Ownable(initialOwner) {}

    function setRelayer(address _relayer) external onlyOwner {
        relayer = _relayer;
    }

    // Client funds the job on Chain A
    function registerAndFundJob(
        string calldata cid,
        uint256 minCpu,
        uint256 minGpuVram,
        uint256 minRam
    ) external payable returns (uint256 jobId) {
        require(msg.value > 0, "Budget must be greater than 0");
        
        jobId = nextJobId++;
        jobEscrows[jobId] = msg.value;

        emit CrossChainJobFunded(jobId, msg.sender, msg.value, cid, minCpu, minGpuVram, minRam);
        return jobId;
    }

    // Relayer triggers payment to worker on Chain A after completion on Chain B
    function releasePayment(uint256 jobId, address worker) external onlyRelayer {
        uint256 amount = jobEscrows[jobId];
        require(amount > 0, "No funds escrowed for this job");
        
        jobEscrows[jobId] = 0;
        
        (bool success, ) = worker.call{value: amount}("");
        require(success, "Payment transfer failed");

        emit JobPayoutReleased(jobId, worker, amount);
    }
}
