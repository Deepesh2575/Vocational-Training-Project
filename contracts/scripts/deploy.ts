import { ethers } from "hardhat";

async function main() {
  console.log("Deploying Groth16Verifier...");
  const Groth16Verifier = await ethers.getContractFactory("Groth16Verifier");
  const verifier = await Groth16Verifier.deploy();
  await verifier.waitForDeployment();
  const verifierAddress = await verifier.getAddress();
  console.log(`Groth16Verifier deployed to: ${verifierAddress}`);

  console.log("Deploying ProtocolGovernance...");
  const [deployer] = await ethers.getSigners();
  const ProtocolGovernance = await ethers.getContractFactory("ProtocolGovernance");
  const governance = await ProtocolGovernance.deploy(deployer.address);
  await governance.waitForDeployment();
  const govAddress = await governance.getAddress();
  console.log(`ProtocolGovernance deployed to: ${govAddress}`);

  console.log("Deploying ClientGateway...");
  const ClientGateway = await ethers.getContractFactory("ClientGateway");
  const clientGateway = await ClientGateway.deploy(deployer.address);
  await clientGateway.waitForDeployment();
  const gatewayAddress = await clientGateway.getAddress();
  console.log(`ClientGateway deployed to: ${gatewayAddress}`);
  // Set relayer to deployer for local testing
  await clientGateway.setRelayer(deployer.address);
  console.log(`Set Relayer on ClientGateway to: ${deployer.address}`);

  console.log("Deploying JobOrchestrator (initially owned by deployer for fast setup)...");
  const JobOrchestrator = await ethers.getContractFactory("JobOrchestrator");
  const jobOrchestrator = await JobOrchestrator.deploy(verifierAddress, deployer.address);

  await jobOrchestrator.waitForDeployment();

  const address = await jobOrchestrator.getAddress();
  console.log(`JobOrchestrator deployed to: ${address}`);

  console.log("Setting Relayer on Orchestrator...");
  let tx1 = await jobOrchestrator.setRelayer(deployer.address);
  await tx1.wait();
  console.log(`Relayer set on JobOrchestrator to: ${deployer.address}`);

  console.log("Transferring JobOrchestrator ownership to Governance contract...");
  let tx2 = await jobOrchestrator.transferOwnership(govAddress);
  await tx2.wait();
  console.log(`Ownership transferred to ProtocolGovernance (${govAddress}).`);

  const fs = require("fs");
  const path = require("path");
  const addresses = {
    Groth16Verifier: verifierAddress,
    ProtocolGovernance: govAddress,
    ClientGateway: gatewayAddress,
    JobOrchestrator: address
  };
  fs.writeFileSync(
    path.join(__dirname, "..", "deployed_addresses.json"),
    JSON.stringify(addresses, null, 2)
  );
  console.log("Addresses saved to deployed_addresses.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
