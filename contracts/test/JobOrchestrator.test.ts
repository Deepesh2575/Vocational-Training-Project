import { expect } from "chai";
import { ethers } from "hardhat";

describe("JobOrchestrator", function () {
  async function deployFixture() {
    const [owner, client, worker1, worker2] = await ethers.getSigners();
    const JobOrchestratorFactory = await ethers.getContractFactory("JobOrchestrator");
    const contract = await JobOrchestratorFactory.deploy();
    return { contract, owner, client, worker1, worker2 };
  }

  it("Should register a job and open bidding", async function () {
    const { contract, client } = await deployFixture();
    
    await contract.connect(client).registerJob(
      1000, "ipfs://Qhash123", 4, 8, 16
    );

    const job = await contract.getJob(0);
    expect(job.client).to.equal(client.address);
    expect(job.state).to.equal(1); // 1 is BiddingOpen
  });

  it("Should allow workers to bid and client to assign winner", async function () {
    const { contract, client, worker1, worker2 } = await deployFixture();
    
    await contract.connect(client).registerJob(
      1000, "ipfs://Qhash123", 4, 8, 16
    );

    // worker1 bids with stake 500
    await contract.connect(worker1).submitBid(0, 500, 8, 16, 32);
    // worker2 bids with stake 1000
    await contract.connect(worker2).submitBid(0, 1000, 16, 32, 64);

    // Client assigns winner (should pick worker2 because of higher stake)
    await contract.connect(client).assignWinner(0);

    const job = await contract.getJob(0);
    expect(job.assignedWorker).to.equal(worker2.address);
    expect(job.state).to.equal(2); // 2 is Assigned
  });
});
