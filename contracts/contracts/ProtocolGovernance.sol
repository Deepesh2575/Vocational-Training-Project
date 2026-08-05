// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

contract ProtocolGovernance is Ownable {
    uint256 public constant MIN_DELAY = 1 days;

    struct Proposal {
        address target;
        bytes data;
        uint256 executeTime;
        bool executed;
    }

    mapping(uint256 => Proposal) public proposals;
    uint256 public nextProposalId;

    event ProposalCreated(uint256 indexed proposalId, address target, bytes data, uint256 executeTime);
    event ProposalExecuted(uint256 indexed proposalId, address target, bytes data);

    constructor(address initialOwner) Ownable(initialOwner) {}

    function propose(address target, bytes calldata data) external onlyOwner returns (uint256) {
        uint256 proposalId = nextProposalId++;
        uint256 executeTime = block.timestamp + MIN_DELAY;
        
        proposals[proposalId] = Proposal({
            target: target,
            data: data,
            executeTime: executeTime,
            executed: false
        });

        emit ProposalCreated(proposalId, target, data, executeTime);
        return proposalId;
    }

    function execute(uint256 proposalId) external onlyOwner {
        Proposal storage proposal = proposals[proposalId];
        require(!proposal.executed, "Already executed");
        require(block.timestamp >= proposal.executeTime, "Timelock not expired");

        proposal.executed = true;

        (bool success, bytes memory returnData) = proposal.target.call(proposal.data);
        if (!success) {
            if (returnData.length > 0) {
                assembly {
                    let returnData_size := mload(returnData)
                    revert(add(32, returnData), returnData_size)
                }
            } else {
                revert("Governance transaction failed");
            }
        }

        emit ProposalExecuted(proposalId, proposal.target, proposal.data);
    }
}
