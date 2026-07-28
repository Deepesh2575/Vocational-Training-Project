import { ethers } from "hardhat";

async function main() {
  console.log("Deploying MockGroth16Verifier...");
  const MockGroth16Verifier = await ethers.getContractFactory("MockGroth16Verifier");
  const verifier = await MockGroth16Verifier.deploy();
  await verifier.waitForDeployment();
  const verifierAddress = await verifier.getAddress();
  console.log(`MockGroth16Verifier deployed to: ${verifierAddress}`);

  console.log("Deploying JobOrchestrator...");
  const JobOrchestrator = await ethers.getContractFactory("JobOrchestrator");
  const jobOrchestrator = await JobOrchestrator.deploy(verifierAddress);

  await jobOrchestrator.waitForDeployment();

  const address = await jobOrchestrator.getAddress();
  console.log(`JobOrchestrator deployed to: ${address}`);

  const fs = require("fs");
  const path = require("path");
  const addresses = {
    MockGroth16Verifier: verifierAddress,
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
