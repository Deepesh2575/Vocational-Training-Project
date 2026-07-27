@echo off
echo Starting Decentralized Compute Network MVP...
echo.

:: 1. Start Hardhat Node
echo Starting Local Blockchain...
start "Blockchain Node" cmd /k "cd contracts && npx hardhat node"

:: Give the node a couple seconds to boot
timeout /t 3 /nobreak >nul

:: 2. Deploy Contract
echo Deploying Smart Contract...
start "Deploy Contract" cmd /c "cd contracts && npx hardhat run scripts/deploy.ts --network localhost && echo Contract Deployed! You may close this window. && pause"

:: Give the deployment a moment to finish
timeout /t 3 /nobreak >nul

:: 3. Start Mock IPFS
echo Starting IPFS Gateway...
start "IPFS Server" cmd /k ".venv\Scripts\python.exe apps\mock_ipfs.py"

:: 4. Start Worker Node
echo Starting Confidential Worker...
start "Worker Node" cmd /k "cd apps\worker-runtime && ..\..\.venv\Scripts\python.exe worker.py"

:: Give the worker a second to connect
timeout /t 2 /nobreak >nul

:: 5. Start Client SDK
echo Starting Client...
start "Client SDK" cmd /k "cd apps\client-sdk && ..\..\.venv\Scripts\python.exe client.py"

echo.
echo All components have been started in separate windows!
echo Watch the "Client SDK" and "Worker Node" windows to see the magic happen.
pause
