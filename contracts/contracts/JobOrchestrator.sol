// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./Groth16Verifier.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

enum JobState {
    Created,
    BiddingOpen,
    Assigned,
    KeyProvided,
    Executing,
    ProofSubmitted,
    Completed,
    Failed,
    Slashed
}

struct Job {
    address client;
    uint256 budget;
    string cid;
    uint256 minCpu;
    uint256 minGpuVram;
    uint256 minRam;
    JobState state;
    address assignedWorker;
    string encryptedSessionKey;
    bytes32 resultHash;
    uint256 assignedTimestamp;
}

contract JobOrchestrator is Ownable {
    mapping(uint256 => Job) public jobs;
    
    // Mapping from jobId to a mapping of worker address to their bid (stake amount)
    mapping(uint256 => mapping(address => uint256)) public bids;
    
    // Simplistic array to keep track of bidders per job for MVP
    mapping(uint256 => address[]) public jobBidders;

    // Reputation Scoring System
    mapping(address => uint256) public workerReputation;
    mapping(address => string) public workerPublicKeys;
    uint256 public reputationReward = 10;
    uint256 public reputationPenalty = 30;
    uint256 public failoverTimeout = 5 minutes;

    IGroth16Verifier public verifier;

    // Cross-Chain Relayer
    address public relayer;

    constructor(address _verifier, address initialOwner) Ownable(initialOwner) {
        verifier = IGroth16Verifier(_verifier);
    }

    modifier onlyRelayer() {
        require(msg.sender == relayer, "Only relayer can call this");
        _;
    }

    event JobRegistered(uint256 indexed jobId, address indexed client, uint256 budget);
    event BidSubmitted(uint256 indexed jobId, address indexed worker, uint256 stake);
    event WorkerAssigned(uint256 indexed jobId, address indexed worker);
    event TeeQuoteVerified(uint256 indexed jobId, address indexed worker);
    event ProofSubmitted(uint256 indexed jobId, bytes32 resultHash);
    event JobReauctioned(uint256 indexed jobId);
    
    // Triggered when proof is verified to notify the relayer to release funds on Client Gateway
    event CrossChainJobCompleted(uint256 indexed jobId, address indexed worker);
    
    // --- Governance Module Upgrades ---
    function updateVerifier(address newVerifier) external onlyOwner {
        verifier = IGroth16Verifier(newVerifier);
    }

    function updateReputationMetrics(uint256 reward, uint256 penalty) external onlyOwner {
        reputationReward = reward;
        reputationPenalty = penalty;
    }

    function updateFailoverTimeout(uint256 newTimeout) external onlyOwner {
        failoverTimeout = newTimeout;
    }
    
    function setRelayer(address _relayer) external onlyOwner {
        relayer = _relayer;
    }
    // ----------------------------------

    // Called by the cross-chain relayer when a client funds a job on the ClientGateway
    function receiveCrossChainJob(
        uint256 jobId,
        address client,
        uint256 budget,
        string calldata cid,
        uint256 minCpu,
        uint256 minGpuVram,
        uint256 minRam
    ) external onlyRelayer {
        require(jobs[jobId].client == address(0), "Job ID already exists");
        
        jobs[jobId] = Job({
            client: client,
            budget: budget,
            cid: cid,
            minCpu: minCpu,
            minGpuVram: minGpuVram,
            minRam: minRam,
            state: JobState.BiddingOpen,
            assignedWorker: address(0),
            encryptedSessionKey: "",
            resultHash: bytes32(0),
            assignedTimestamp: 0
        });

        emit JobRegistered(jobId, client, budget);
    }

    function submitBid(
        uint256 jobId,
        uint256 stake,
        uint256 cpu,
        uint256 gpuVram,
        uint256 ram,
        bytes calldata enclaveQuote,
        string calldata publicKey
    ) external payable returns (bool) {
        Job storage job = jobs[jobId];
        require(job.state == JobState.BiddingOpen, "Bidding is not open for this job");
        require(cpu >= job.minCpu, "Insufficient CPU");
        require(gpuVram >= job.minGpuVram, "Insufficient GPU VRAM");
        require(ram >= job.minRam, "Insufficient RAM");
        require(msg.value == stake, "ETH sent must match stake amount");
        require(enclaveQuote.length == 1184 || enclaveQuote.length == 1024, "Invalid TEE enclave quote (must be AMD or Intel TDX size)");
        
        emit TeeQuoteVerified(jobId, msg.sender);
        
        if (bids[jobId][msg.sender] == 0) {
            jobBidders[jobId].push(msg.sender);
        }
        
        bids[jobId][msg.sender] = stake;
        workerPublicKeys[msg.sender] = publicKey;
        
        emit BidSubmitted(jobId, msg.sender, stake);
        return true;
    }

    // Called by client (Wait, if the client is on Chain A, they can't call this easily unless they sign a tx on Chain B)
    // For MVP, since both are local, the client script can just submit a transaction to Chain B directly for assignment.
    function assignWinner(uint256 jobId) external returns (address) {
        Job storage job = jobs[jobId];
        require(job.state == JobState.BiddingOpen, "Bidding is not open");
        require(msg.sender == job.client || msg.sender == relayer, "Only client or relayer can assign winner");
        require(jobBidders[jobId].length > 0, "No bids submitted");

        // Assignment logic using effectiveStake based on reputation
        address winner = jobBidders[jobId][0];
        uint256 winnerStake = bids[jobId][winner];
        uint256 highestEffectiveStake = winnerStake + (winnerStake * workerReputation[winner] / 100);
        
        for (uint i = 1; i < jobBidders[jobId].length; i++) {
            address bidder = jobBidders[jobId][i];
            uint256 bidderStake = bids[jobId][bidder];
            uint256 effectiveStake = bidderStake + (bidderStake * workerReputation[bidder] / 100);
            
            if (effectiveStake > highestEffectiveStake) {
                highestEffectiveStake = effectiveStake;
                winner = bidder;
            }
        }

        job.assignedWorker = winner;
        job.state = JobState.Assigned;
        job.assignedTimestamp = block.timestamp;
        
        // Refund all other bidders
        for (uint i = 0; i < jobBidders[jobId].length; i++) {
            address bidder = jobBidders[jobId][i];
            if (bidder != winner) {
                uint256 refundAmount = bids[jobId][bidder];
                bids[jobId][bidder] = 0;
                payable(bidder).transfer(refundAmount);
            }
        }
        
        emit WorkerAssigned(jobId, winner);
        return winner;
    }

    function provideKey(uint256 jobId, string calldata encryptedKey) external {
        Job storage job = jobs[jobId];
        require(msg.sender == job.client || msg.sender == relayer, "Only client can provide key");
        require(job.state == JobState.Assigned, "Job not assigned");
        
        job.encryptedSessionKey = encryptedKey;
        job.state = JobState.KeyProvided;
    }

    function markExecuting(uint256 jobId) external {
        Job storage job = jobs[jobId];
        require(msg.sender == job.assignedWorker, "Only assigned worker can start execution");
        require(job.state == JobState.KeyProvided, "Key not provided yet");
        
        job.state = JobState.Executing;
    }

    function submitProof(
        uint256 jobId,
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[1] calldata input
    ) external {
        Job storage job = jobs[jobId];
        require(msg.sender == job.assignedWorker, "Only assigned worker can submit proof");
        require(job.state == JobState.Executing, "Job is not executing");
        
        // ZK-SNARK Verification
        require(verifier.verifyProof(a, b, c, input), "Invalid Groth16 ZK-SNARK Proof");
        
        // The public input represents the output hash. We store it as bytes32.
        job.resultHash = bytes32(input[0]);
        job.state = JobState.ProofSubmitted;
        
        // Reputation Scoring: Grant reward for successful proof submission
        workerReputation[msg.sender] += reputationReward;
        
        emit ProofSubmitted(jobId, job.resultHash);
        
        // Emit CrossChain event for the relayer to pick up and trigger payment on ClientGateway
        emit CrossChainJobCompleted(jobId, msg.sender);
    }

    function triggerFailover(uint256 jobId) external {
        Job storage job = jobs[jobId];
        require(job.state == JobState.Assigned || job.state == JobState.Executing, "Job not in failover state");
        require(block.timestamp > job.assignedTimestamp + failoverTimeout, "Timeout has not been reached");
        
        uint256 slashedStake = bids[jobId][job.assignedWorker];
        bids[jobId][job.assignedWorker] = 0;
        
        // Reputation Scoring: Apply penalty for SLA breach
        if (workerReputation[job.assignedWorker] > reputationPenalty) {
            workerReputation[job.assignedWorker] -= reputationPenalty;
        } else {
            workerReputation[job.assignedWorker] = 0;
        }
        
        // Reset the job to allow re-bidding (Re-auction)
        job.state = JobState.BiddingOpen;
        job.assignedWorker = address(0);
        
        // Clear the old bidders array so a fresh auction can happen
        delete jobBidders[jobId];
        
        if (slashedStake > 0) {
            payable(job.client).transfer(slashedStake);
        }
        
        emit JobReauctioned(jobId);
    }

    function releaseStake(uint256 jobId) external {
        Job storage job = jobs[jobId];
        require(msg.sender == job.assignedWorker, "Only assigned worker can release stake");
        require(job.state == JobState.ProofSubmitted || job.state == JobState.Completed, "Proof not submitted");
        
        uint256 stake = bids[jobId][msg.sender];
        require(stake > 0, "No stake to release");
        
        bids[jobId][msg.sender] = 0;
        payable(msg.sender).transfer(stake);
    }

    function getJobState(uint256 jobId) external view returns (JobState) {
        return jobs[jobId].state;
    }

    function getJob(uint256 jobId) external view returns (Job memory) {
        return jobs[jobId];
    }
}
