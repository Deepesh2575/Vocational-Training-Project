import { ethers } from "hardhat";

async function main() {
  console.log("Deploying JobOrchestrator...");
  const JobOrchestrator = await ethers.getContractFactory("JobOrchestrator");
  const jobOrchestrator = await JobOrchestrator.deploy();

  await jobOrchestrator.waitForDeployment();

  const address = await jobOrchestrator.getAddress();
  console.log(`JobOrchestrator deployed to: ${address}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
