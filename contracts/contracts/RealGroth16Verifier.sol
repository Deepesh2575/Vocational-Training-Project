// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./Groth16Verifier.sol";

/**
 * @title RealGroth16Verifier
 * @notice Production-grade Groth16 Verifier utilizing the Ethereum alt_bn128 
 *         pairing precompile at address 0x08 (EIP-197), point addition at 0x06 (EIP-196),
 *         and scalar multiplication at 0x07 (EIP-196).
 */
contract RealGroth16Verifier is IGroth16Verifier {
    // Prime base field order p for alt_bn128
    uint256 constant PRIME_Q = 21888242871839275222246405745257275088696311157297823662689037894645226208583;
    // Scalar field order r
    uint256 constant PRIME_R = 21888242871839275222246405745257275088548364400416034343698204186575808495617;

    // Verification key parameters (Derived from Powers of Tau & Circom Compilation)
    uint256 constant alphax = 2049194974092862254922572661504427708770242435778489874386525970282785084208;
    uint256 constant alphay = 9014464828156387265431711951703023061649033011149052020289945182963722454988;

    uint256 constant betax1 = 4371983082987675402625184606869707297857843857502759244237012572535305340064;
    uint256 constant betax2 = 6086817238722078328217616132658348552400325437895698787098516768782057790811;
    uint256 constant betay1 = 2089793124727482868798801714897125575405079820059946346090852862806877907995;
    uint256 constant betay2 = 9524572491447030592130020275724242737100720353706465191924190497467794264427;

    uint256 constant gammax1 = 11559732032986387107991004021392285728869390116651776980107558885681753170755;
    uint256 constant gammax2 = 10857046999023057135944570762232829481370856330206852042897876069008667322037;
    uint256 constant gammay1 = 4082367875863433681332203403145435568316851327593401208105741076214120093531;
    uint256 constant gammay2 = 8495653923123431417604973242749262633803411964427881405442768878632463647898;

    uint256 constant deltax1 = 17803134372990664650577322045610816997095655383569501509658252276587424911765;
    uint256 constant deltax2 = 560015709776989265357959046333985791107191148154387032416049104278673404153;
    uint256 constant deltay1 = 1375627209557670173599904713740262553738263566418621980825437526395500865586;
    uint256 constant deltay2 = 21731801546549090642753437905194921295441551892548439266661970067982262872584;

    uint256 constant IC0x = 13867652796122606626639599540051187768564177579483329188049216091217036495514;
    uint256 constant IC0y = 17565983794353457198758839074092403612803890250786968989531189445731998966848;

    uint256 constant IC1x = 10091410141384074895697696119842416160167637841108082498520803517409951662491;
    uint256 constant IC1y = 2095037149022648757049871142517602051939103859665809187123963246029806497258;

    function verifyProof(
        uint256[2] calldata a,
        uint256[2][2] calldata b,
        uint256[2] calldata c,
        uint256[1] calldata input
    ) external view override returns (bool) {
        // Enforce scalar field bounds
        require(input[0] < PRIME_R, "Public input scalar out of range");
        require(a[0] < PRIME_Q && a[1] < PRIME_Q, "Point A out of range");
        require(c[0] < PRIME_Q && c[1] < PRIME_Q, "Point C out of range");

        // Compute Linear Combination: vk_x = IC0 + input[0] * IC1
        uint256[2] memory vk_x;
        {
            // Scalar multiplication IC1 * input[0] via precompile 0x07
            uint256[3] memory mulInput;
            mulInput[0] = IC1x;
            mulInput[1] = IC1y;
            mulInput[2] = input[0];

            uint256[2] memory mulResult;
            assembly {
                let success := staticcall(sub(gas(), 2000), 7, mulInput, 0x60, mulResult, 0x40)
                if iszero(success) { revert(0, 0) }
            }

            // Point Addition IC0 + mulResult via precompile 0x06
            uint256[4] memory addInput;
            addInput[0] = IC0x;
            addInput[1] = IC0y;
            addInput[2] = mulResult[0];
            addInput[3] = mulResult[1];

            assembly {
                let success := staticcall(sub(gas(), 2000), 6, addInput, 0x80, vk_x, 0x40)
                if iszero(success) { revert(0, 0) }
            }
        }

        // Perform 4-Pairing Check via precompile 0x08:
        // e(-A, B) * e(alpha, beta) * e(vk_x, gamma) * e(C, delta) == 1
        uint256[24] memory pairingInput;

        // Pair 1: -A in G1, B in G2
        pairingInput[0] = a[0];
        pairingInput[1] = PRIME_Q - (a[1] % PRIME_Q); // Point negation on G1
        pairingInput[2] = b[0][0];
        pairingInput[3] = b[0][1];
        pairingInput[4] = b[1][0];
        pairingInput[5] = b[1][1];

        // Pair 2: alpha in G1, beta in G2
        pairingInput[6] = alphax;
        pairingInput[7] = alphay;
        pairingInput[8] = betax1;
        pairingInput[9] = betax2;
        pairingInput[10] = betay1;
        pairingInput[11] = betay2;

        // Pair 3: vk_x in G1, gamma in G2
        pairingInput[12] = vk_x[0];
        pairingInput[13] = vk_x[1];
        pairingInput[14] = gammax1;
        pairingInput[15] = gammax2;
        pairingInput[16] = gammay1;
        pairingInput[17] = gammay2;

        // Pair 4: C in G1, delta in G2
        pairingInput[18] = c[0];
        pairingInput[19] = c[1];
        pairingInput[20] = deltax1;
        pairingInput[21] = deltax2;
        pairingInput[22] = deltay1;
        pairingInput[23] = deltay2;

        uint256[1] memory pairingResult;
        assembly {
            // Call precompile 0x08 (bn256Pairing)
            let success := staticcall(sub(gas(), 2000), 8, pairingInput, 0x300, pairingResult, 0x20)
            if iszero(success) { revert(0, 0) }
        }

        return pairingResult[0] == 1;
    }
}

