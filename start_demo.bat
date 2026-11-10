@echo off
echo Starting Decentralized Compute Network MVP...
echo.

:: 1. Start Hardhat Node
echo Starting Local Blockchain...
start "Blockchain Node" cmd /k "cd contracts && npx hardhat node"

:: Give the node a couple seconds to boot
timeout /t 3 /nobreak >nul

:: 2. Deploy Contract
echo Deploying Smart Contracts...
start "Deploy Contract" cmd /c "cd contracts && npx hardhat run scripts/deploy.ts --network localhost && echo Contract Deployed! You may close this window. && pause"

:: Give the deployment a moment to finish
timeout /t 4 /nobreak >nul

:: 3. Start Mock IPFS
echo Starting IPFS Gateway...
start "IPFS Server" cmd /k ".venv\Scripts\python.exe apps\mock_ipfs.py"

:: Give IPFS a moment to boot
timeout /t 2 /nobreak >nul

:: 4. Start Cross-Chain Relayer Daemon
echo Starting Cross-Chain Relayer...
start "Cross-Chain Relayer" cmd /k ".venv\Scripts\python.exe apps\relayer\relayer.py"

:: Give the relayer a moment to connect
timeout /t 2 /nobreak >nul

:: 5. Start Worker Node
echo Starting Confidential Worker...
start "Worker Node" cmd /k "cd apps\worker-runtime && ..\..\.venv\Scripts\python.exe worker.py"

:: Give the worker a second to connect
timeout /t 3 /nobreak >nul

:: 6. Start Client SDK
echo Starting Client...
start "Client SDK" cmd /k "cd apps\client-sdk && ..\..\.venv\Scripts\python.exe client.py"

echo.
echo ========================================================
echo All 5 components have been successfully initialized!
echo 1. Blockchain (Hardhat local EVM node)
echo 2. IPFS Storage Gateway
echo 3. Cross-Chain Relayer (Bridges Gateway to Orchestrator)
echo 4. Confidential Worker Node (PQC identity + Enclave runtime)
echo 5. Client SDK (CKKS FHE encryption + PQC ML-KEM encapsulation)
echo ========================================================
echo Watch the "Client SDK" and "Worker Node" windows to see the live execution.
pause
