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
    uint256 assignedTimestamp;
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
    ) external payable returns (bool);

    function assignWinner(uint256 jobId) external returns (address);

    function markExecuting(uint256 jobId) external;

    function submitProof(uint256 jobId, bytes32 proofHash) external;
    
    function slashWorker(uint256 jobId) external;
    
    function releaseStake(uint256 jobId) external;

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
            resultHash: bytes32(0),
            assignedTimestamp: 0
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
    ) external payable override returns (bool) {
        Job storage job = jobs[jobId];
        require(job.state == JobState.BiddingOpen, "Bidding is not open for this job");
        require(cpu >= job.minCpu, "Insufficient CPU");
        require(gpuVram >= job.minGpuVram, "Insufficient GPU VRAM");
        require(ram >= job.minRam, "Insufficient RAM");
        require(msg.value == stake, "ETH sent must match stake amount");
        
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

    function slashWorker(uint256 jobId) external override {
        Job storage job = jobs[jobId];
        require(job.state == JobState.Assigned || job.state == JobState.Executing, "Job not in slashable state");
        require(block.timestamp > job.assignedTimestamp + 5 minutes, "Timeout has not been reached");
        
        uint256 slashedStake = bids[jobId][job.assignedWorker];
        bids[jobId][job.assignedWorker] = 0;
        
        job.state = JobState.Slashed;
        
        if (slashedStake > 0) {
            payable(job.client).transfer(slashedStake);
        }
    }

    function releaseStake(uint256 jobId) external override {
        Job storage job = jobs[jobId];
        require(msg.sender == job.assignedWorker, "Only assigned worker can release stake");
        require(job.state == JobState.ProofSubmitted || job.state == JobState.Completed, "Proof not submitted");
        
        uint256 stake = bids[jobId][msg.sender];
        require(stake > 0, "No stake to release");
        
        bids[jobId][msg.sender] = 0;
        payable(msg.sender).transfer(stake);
    }

    function getJobState(uint256 jobId) external view override returns (JobState) {
        return jobs[jobId].state;
    }

    function getJob(uint256 jobId) external view override returns (Job memory) {
        return jobs[jobId];
    }
}
