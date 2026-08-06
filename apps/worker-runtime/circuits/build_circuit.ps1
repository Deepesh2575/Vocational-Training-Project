cd "c:\Users\DEEPESH\Downloads\VT  project 2\apps\worker-runtime\circuits"

Write-Host "Compiling circom circuit..."
npx circom multiplier.circom --r1cs --wasm --sym -o .

Write-Host "Performing trusted setup phase 1..."
npx snarkjs powersoftau new bn128 12 pot12_0000.ptau -v
npx snarkjs powersoftau contribute pot12_0000.ptau pot12_0001.ptau --name="First contribution" -v -e="random text"
npx snarkjs powersoftau prepare phase2 pot12_0001.ptau pot12_final.ptau -v

Write-Host "Performing trusted setup phase 2..."
npx snarkjs groth16 setup multiplier.r1cs pot12_final.ptau multiplier_0000.zkey
npx snarkjs zkey contribute multiplier_0000.zkey multiplier_final.zkey --name="Second contribution" -v -e="another random text"

Write-Host "Exporting verification key and Solidity verifier..."
npx snarkjs zkey export verificationkey multiplier_final.zkey verification_key.json
npx snarkjs zkey export solidityverifier multiplier_final.zkey Verifier.sol

Write-Host "Copying Verifier.sol to contracts folder..."
Copy-Item Verifier.sol -Destination "..\..\..\contracts\contracts\" -Force

Write-Host "Build complete!"
