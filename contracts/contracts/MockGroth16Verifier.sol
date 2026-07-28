// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IGroth16Verifier {
    function verifyProof(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[1] calldata input
    ) external view returns (bool);
}

contract MockGroth16Verifier is IGroth16Verifier {
    uint256 constant p = 21888242871839275222246405745257275088696311157297823662689037894645226208583;

    function verifyProof(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[1] calldata input
    ) external view override returns (bool) {
        // Ensure non-zero parameters are provided
        require(b[0][0] != 0 || b[0][1] != 0, "Point B must be non-zero");
        require(input[0] != 0, "Input cannot be zero");

        // Mathematical verification: Assert that points A and C are mathematically valid 
        // group elements lying on the Ethereum alt_bn128 curve: y^2 = x^3 + 3 (mod p)
        require(isOnCurveG1(a[0], a[1]), "Point A is not on alt_bn128 curve");
        require(isOnCurveG1(c[0], c[1]), "Point C is not on alt_bn128 curve");

        // Since we are mocking the pairing check for MVP, we return true if they are on-curve
        return true;
    }

    function isOnCurveG1(uint256 x, uint256 y) internal pure returns (bool) {
        require(x < p && y < p, "Coordinates out of bounds for prime field");
        // lhs = y^2 mod p
        uint256 lhs = mulmod(y, y, p);
        // rhs = x^3 + 3 mod p
        uint256 x3 = mulmod(x, mulmod(x, x, p), p);
        uint256 rhs = addmod(x3, 3, p);
        
        return lhs == rhs;
    }
}
