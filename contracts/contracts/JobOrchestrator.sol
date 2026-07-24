// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

enum JobState {
    Created,
    BiddingOpen,
    Assigned,
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
    bytes32 resultHash;
}

interface IJobOrchestrator {
    function registerJob(
        uint256 budget,
        string calldata cid,
        uint256 minCpu,
        uint256 minGpuVram,
        uint256 minRam
    ) external returns (uint256 jobId);

    function submitBid(
        uint256 jobId,
        uint256 stake,
        uint256 cpu,
        uint256 gpuVram,
        uint256 ram
    ) external returns (bool);

    function assignWinner(uint256 jobId) external returns (address);

    function markExecuting(uint256 jobId) external;

    function submitProof(uint256 jobId, bytes32 proofHash) external;

    function getJobState(uint256 jobId) external view returns (JobState);

    function getJob(uint256 jobId) external view returns (Job memory);
}

contract JobOrchestrator is IJobOrchestrator {
    uint256 private nextJobId;
    mapping(uint256 => Job) public jobs;
    
    // Mapping from jobId to a mapping of worker address to their bid (stake amount)
    mapping(uint256 => mapping(address => uint256)) public bids;
    
    // Simplistic array to keep track of bidders per job for MVP
    mapping(uint256 => address[]) public jobBidders;

    event JobRegistered(uint256 indexed jobId, address indexed client, uint256 budget);
    event BidSubmitted(uint256 indexed jobId, address indexed worker, uint256 stake);
    event WorkerAssigned(uint256 indexed jobId, address indexed worker);

    function registerJob(
        uint256 budget,
        string calldata cid,
        uint256 minCpu,
        uint256 minGpuVram,
        uint256 minRam
    ) external override returns (uint256 jobId) {
        jobId = nextJobId++;
        
        jobs[jobId] = Job({
            client: msg.sender,
            budget: budget,
            cid: cid,
            minCpu: minCpu,
            minGpuVram: minGpuVram,
            minRam: minRam,
            state: JobState.BiddingOpen,
            assignedWorker: address(0),
            resultHash: bytes32(0)
        });

        emit JobRegistered(jobId, msg.sender, budget);
        return jobId;
    }

    function submitBid(
        uint256 jobId,
        uint256 stake,
        uint256 cpu,
        uint256 gpuVram,
        uint256 ram
    ) external override returns (bool) {
        Job storage job = jobs[jobId];
        require(job.state == JobState.BiddingOpen, "Bidding is not open for this job");
        require(cpu >= job.minCpu, "Insufficient CPU");
        require(gpuVram >= job.minGpuVram, "Insufficient GPU VRAM");
        require(ram >= job.minRam, "Insufficient RAM");
        
        if (bids[jobId][msg.sender] == 0) {
            jobBidders[jobId].push(msg.sender);
        }
        
        bids[jobId][msg.sender] = stake;
        
        emit BidSubmitted(jobId, msg.sender, stake);
        return true;
    }

    function assignWinner(uint256 jobId) external override returns (address) {
        Job storage job = jobs[jobId];
        require(job.state == JobState.BiddingOpen, "Bidding is not open");
        require(msg.sender == job.client, "Only client can assign winner");
        require(jobBidders[jobId].length > 0, "No bids submitted");

        // MVP: Simple assignment logic - pick the one with highest stake
        address winner = jobBidders[jobId][0];
        uint256 highestStake = bids[jobId][winner];
        
        for (uint i = 1; i < jobBidders[jobId].length; i++) {
            address bidder = jobBidders[jobId][i];
            uint256 bidderStake = bids[jobId][bidder];
            if (bidderStake > highestStake) {
                highestStake = bidderStake;
                winner = bidder;
            }
        }

        job.assignedWorker = winner;
        job.state = JobState.Assigned;
        
        emit WorkerAssigned(jobId, winner);
        return winner;
    }

    function markExecuting(uint256 jobId) external override {
        Job storage job = jobs[jobId];
        require(msg.sender == job.assignedWorker, "Only assigned worker can start execution");
        require(job.state == JobState.Assigned, "Job not assigned");
        
        job.state = JobState.Executing;
    }

    function submitProof(uint256 jobId, bytes32 proofHash) external override {
        Job storage job = jobs[jobId];
        require(msg.sender == job.assignedWorker, "Only assigned worker can submit proof");
        require(job.state == JobState.Executing, "Job is not executing");
        
        job.resultHash = proofHash;
        job.state = JobState.ProofSubmitted;
    }

    function getJobState(uint256 jobId) external view override returns (JobState) {
        return jobs[jobId].state;
    }

    function getJob(uint256 jobId) external view override returns (Job memory) {
        return jobs[jobId];
    }
}
