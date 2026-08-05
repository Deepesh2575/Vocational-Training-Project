import { ethers } from "hardhat";

async function main() {
  const fs = require("fs");
  const path = require("path");
  const addressesPath = path.join(__dirname, "..", "deployed_addresses.json");
  const addresses = JSON.parse(fs.readFileSync(addressesPath, "utf8"));

  const JobOrchestrator = await ethers.getContractFactory("JobOrchestrator");
  const orchestrator = JobOrchestrator.attach(addresses.JobOrchestrator);

  const workerAddress = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8";
  
  const rep = await orchestrator.workerReputation(workerAddress);
  console.log(`Worker Reputation for ${workerAddress}: ${rep.toString()}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
