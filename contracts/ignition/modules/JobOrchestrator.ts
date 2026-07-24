import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

const JobOrchestratorModule = buildModule("JobOrchestratorModule", (m) => {
  const jobOrchestrator = m.contract("JobOrchestrator");

  return { jobOrchestrator };
});

export default JobOrchestratorModule;
