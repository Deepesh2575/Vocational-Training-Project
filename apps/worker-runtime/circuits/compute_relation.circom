pragma circom 2.0.0;

include "node_modules/circomlib/circuits/poseidon.circom";

/**
 * @title ComputeRelation
 * @notice Commits to the private input (c_x = Hash(x, r)),
 *         evaluates an integer/fixed-point function y = x^2 + 10,
 *         and commits to the computation output (c_y = Hash(y)).
 */
template ComputeRelation() {
    // Private input and blinding randomness
    signal input x;
    signal input r;

    // Public commitments: c_x = Hash(x, r) and c_y = Hash(y)
    signal output c_x;
    signal output c_y;

    // 1. Commit to input: c_x = Poseidon(x, r)
    component inHasher = Poseidon(2);
    inHasher.inputs[0] <== x;
    inHasher.inputs[1] <== r;
    c_x <== inHasher.out;

    // 2. Integer function: y = x^2 + 10
    signal x_sq;
    x_sq <== x * x;
    signal y;
    y <== x_sq + 10;

    // 3. Hash the output: c_y = Poseidon(y)
    component outHasher = Poseidon(1);
    outHasher.inputs[0] <== y;
    c_y <== outHasher.out;
}

component main = ComputeRelation();

