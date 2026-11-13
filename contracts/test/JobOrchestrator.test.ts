import { expect } from "chai";
import { ethers } from "hardhat";

describe("JobOrchestrator & Groth16 Verifier Suite", function () {
  // Production SnarkJS Groth16 proof generated for ComputeRelation circuit
  // x = 5, r = 123456789 => c_x = Poseidon(5, 123456789), c_y = Poseidon(35)
  const validA: [string, string] = [
    "0x142f40e34757e87fa501c009b8c8a6ac7134061edf80170fcb34de2aa203e5f5",
    "0x0c8a289c4c13a121430444de4bfb35b581afe654cfc4860bc1d5805cfb87ae83"
  ];
  const validB: [[string, string], [string, string]] = [
    [
      "0x1990db156eb040f2c77d6fe51d7440d25b6d52e33d9364e3716fc19c5ea3031f",
      "0x04f7e2157e424d1162af907e4bfd80de974c8a310258f6a1eaa96664452ed313"
    ],
    [
      "0x1cefbef36bd7abd35180ec7f578f9c6d6f8e6a636f1595b3565831d88d48d041",
      "0x2931a78aea68d8d5d1f681fb1cf3f525d629009c2345b7709dbfe9eb5f99d9f3"
    ]
  ];
  const validC: [string, string] = [
    "0x2b4e4af2348b3188777575bd9ba990b5cc2be7c4ddd921a244b274d5a432d0b0",
    "0x2d400f7436cc5c2fab9e630e764126b25f596bb9d707386fe79db2253f830ef8"
  ];
  const validInputs: [string, string] = [
    "0x19d3f74b859dd36aefb6b1b3d6074c3254d1a5cf3759a1c3b643e1eca8e5014e",
    "0x06d88a8a859841f203aed6147500e91580eceb0a99c5b4b6a5268f1a5c597e17"
  ];

  async function deployFixture() {
    const [owner, client, worker1, worker2] = await ethers.getSigners();
    
    // 1. Deploy Generated SnarkJS Groth16 Verifier
    const VerifierFactory = await ethers.getContractFactory("Groth16Verifier");
    const verifier = await VerifierFactory.deploy();
    await verifier.waitForDeployment();
    
    // 2. Deploy ClientGateway
    const GatewayFactory = await ethers.getContractFactory("ClientGateway");
    const gateway = await GatewayFactory.deploy(owner.address);
    await gateway.waitForDeployment();
    await gateway.setRelayer(owner.address);

    // 3. Deploy JobOrchestrator
    const OrchestratorFactory = await ethers.getContractFactory("JobOrchestrator");
    const orchestrator = await OrchestratorFactory.deploy(await verifier.getAddress(), owner.address);
    await orchestrator.waitForDeployment();
    await orchestrator.setRelayer(owner.address);

    return { verifier, gateway, orchestrator, owner, client, worker1, worker2 };
  }

  it("Should verify that a valid Groth16 proof passes on the generated verifier", async function () {
    const { verifier } = await deployFixture();
    const isValid = await verifier.verifyProof(validA, validB, validC, validInputs);
    expect(isValid).to.be.true;
  });

  it("Should verify that a tampered Groth16 proof reverts or returns false", async function () {
    const { verifier } = await deployFixture();
    
    // 1. Tamper with public output commitment c_y
    const tamperedInputs: [string, string] = [
      validInputs[0],
      "0x06d88a8a859841f203aed6147500e91580eceb0a99c5b4b6a5268f1a5c597e18" // +1 tamper
    ];
    const resultTamperedInput = await verifier.verifyProof(validA, validB, validC, tamperedInputs);
    expect(resultTamperedInput).to.be.false;

    // 2. Tamper with proof point A
    const tamperedA: [string, string] = [
      "0x142f40e34757e87fa501c009b8c8a6ac7134061edf80170fcb34de2aa203e5f6", // +1 tamper
      validA[1]
    ];
    const resultTamperedProof = await verifier.verifyProof(tamperedA, validB, validC, validInputs);
    expect(resultTamperedProof).to.be.false;
  });

  it("Should execute end-to-end job cycle with valid Groth16 proof and gas measurement", async function () {
    const { gateway, orchestrator, owner, client, worker1 } = await deployFixture();

    // 1. Client registers and funds job on Gateway
    const fundTx = await gateway.connect(client).registerAndFundJob("ipfs://QmTestCid", 4, 8, 16, {
      value: ethers.parseEther("0.1")
    });
    await fundTx.wait();

    // 2. Relayer bridges job to JobOrchestrator
    const relayTx = await orchestrator.connect(owner).receiveCrossChainJob(
      0, client.address, ethers.parseEther("0.1"), "ipfs://QmTestCid", 4, 8, 16
    );
    await relayTx.wait();

    let job = await orchestrator.getJob(0);
    expect(job.state).to.equal(1); // BiddingOpen

    // 3. Worker submits bid with mock TEE quote (1024 bytes) and stake (0.001 ETH)
    const mockQuote = ethers.hexlify(ethers.toUtf8Bytes("MOCK_TDX_REPORT_".padEnd(1024, "0")));
    const bidTx = await orchestrator.connect(worker1).submitBid(
      0, ethers.parseEther("0.001"), 8, 16, 32, mockQuote, "kyber_pk_hex:x25519_pk_hex", {
        value: ethers.parseEther("0.001")
      }
    );
    await bidTx.wait();

    // 4. Client / Relayer assigns winner
    const assignTx = await orchestrator.connect(client).assignWinner(0);
    await assignTx.wait();

    job = await orchestrator.getJob(0);
    expect(job.assignedWorker).to.equal(worker1.address);
    expect(job.state).to.equal(2); // Assigned

    // 5. Client provides encrypted key
    const keyTx = await orchestrator.connect(client).provideKey(0, "mock_enc_key");
    await keyTx.wait();

    // 6. Worker marks executing
    const execTx = await orchestrator.connect(worker1).markExecuting(0);
    await execTx.wait();

    // 7. Worker submits valid Groth16 proof
    const proofTx = await orchestrator.connect(worker1).submitProof(0, validA, validB, validC, validInputs);
    await proofTx.wait();

    job = await orchestrator.getJob(0);
    expect(job.state).to.equal(5); // ProofSubmitted
    expect(job.resultHash).to.equal(validInputs[1]);

    // 8. Relayer releases payout to worker on Gateway
    const payTx = await gateway.connect(owner).releasePayment(0, worker1.address);
    await payTx.wait();

    // 9. Worker reclaims stake
    const stakeTx = await orchestrator.connect(worker1).releaseStake(0);
    await stakeTx.wait();

    const rep = await orchestrator.workerReputation(worker1.address);
    expect(rep).to.equal(10n);
  });

  it("Should reject submitProof when caller supplies a tampered Groth16 proof", async function () {
    const { gateway, orchestrator, owner, client, worker1 } = await deployFixture();

    // Register, bid, assign, provide key, mark executing
    await (await gateway.connect(client).registerAndFundJob("ipfs://QmTamperTest", 4, 8, 16, {
      value: ethers.parseEther("0.1")
    })).wait();

    await (await orchestrator.connect(owner).receiveCrossChainJob(
      0, client.address, ethers.parseEther("0.1"), "ipfs://QmTamperTest", 4, 8, 16
    )).wait();

    const mockQuote = ethers.hexlify(ethers.toUtf8Bytes("MOCK_TDX_REPORT_".padEnd(1024, "0")));
    await (await orchestrator.connect(worker1).submitBid(
      0, ethers.parseEther("0.001"), 8, 16, 32, mockQuote, "pk1:pk2", {
        value: ethers.parseEther("0.001")
      }
    )).wait();

    await (await orchestrator.connect(client).assignWinner(0)).wait();
    await (await orchestrator.connect(client).provideKey(0, "mock_enc_key")).wait();
    await (await orchestrator.connect(worker1).markExecuting(0)).wait();

    // Tampered output hash signal
    const tamperedInputs: [string, string] = [
      validInputs[0],
      "0x06d88a8a859841f203aed6147500e91580eceb0a99c5b4b6a5268f1a5c597e18"
    ];

    await expect(
      orchestrator.connect(worker1).submitProof(0, validA, validB, validC, tamperedInputs)
    ).to.be.revertedWith("Invalid Groth16 ZK-SNARK Proof");
  });
});
