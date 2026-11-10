import { expect } from "chai";
import { ethers } from "hardhat";

describe("JobOrchestrator Full Flow & Gas Metering", function () {
  async function deployFixture() {
    const [owner, client, worker1, worker2] = await ethers.getSigners();
    
    // 1. Deploy Verifier
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

  it("Should execute end-to-end job cycle with gas measurement", async function () {
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

    // 7. Worker submits Groth16 proof
    const a: [bigint, bigint] = [1n, 2n];
    const b: [[bigint, bigint], [bigint, bigint]] = [[1n, 2n], [3n, 4n]];
    const c: [bigint, bigint] = [1n, 2n];
    const input: [bigint] = [123456789n];

    const proofTx = await orchestrator.connect(worker1).submitProof(0, a, b, c, input);
    await proofTx.wait();

    job = await orchestrator.getJob(0);
    expect(job.state).to.equal(5); // ProofSubmitted

    // 8. Relayer releases payout to worker on Gateway
    const payTx = await gateway.connect(owner).releasePayment(0, worker1.address);
    await payTx.wait();

    // 9. Worker reclaims stake
    const stakeTx = await orchestrator.connect(worker1).releaseStake(0);
    await stakeTx.wait();

    const rep = await orchestrator.workerReputation(worker1.address);
    expect(rep).to.equal(10n);
  });

  it("Should verify RealGroth16Verifier bounds and elliptic curve validation", async function () {
    const RealVerifierFactory = await ethers.getContractFactory("RealGroth16Verifier");
    const realVerifier = await RealVerifierFactory.deploy();
    await realVerifier.waitForDeployment();

    const a: [bigint, bigint] = [1n, 2n];
    const b: [[bigint, bigint], [bigint, bigint]] = [[1n, 2n], [3n, 4n]];
    const c: [bigint, bigint] = [1n, 2n];
    
    // Test scalar field bound validation
    const invalidScalar = 21888242871839275222246405745257275088548364400416034343698204186575808495618n;
    await expect(
      realVerifier.verifyProof(a, b, c, [invalidScalar])
    ).to.be.revertedWith("Public input scalar out of range");

    // Test base field bound validation on point A
    const invalidPoint = 21888242871839275222246405745257275088696311157297823662689037894645226208584n;
    await expect(
      realVerifier.verifyProof([invalidPoint, 2n], b, c, [123n])
    ).to.be.revertedWith("Point A out of range");
  });
});
