pragma circom 2.0.0;

/**
 * @title VectorPolyEval
 * @dev Verifies the deterministic off-chain computation matching the TenSEAL CKKS
 *      homomorphic transformation: y[i] = x[i]^2 + bias for an N-dimensional vector.
 *      Computes intermediate quadratic constraints and produces an aggregated commitment hash.
 */
template VectorPolyEval(N) {
    // Private input vector components (from decrypted payload)
    signal input x[N];
    
    // Public parameter (bias constant = 10)
    signal input bias;
    
    // Output components
    signal output y[N];
    signal output aggregateDigest;

    // Constraint: Quadratic evaluation x[i] * x[i]
    signal x_sq[N];

    for (var i = 0; i < N; i++) {
        x_sq[i] <== x[i] * x[i];
        y[i] <== x_sq[i] + bias;
    }

    // Accumulate outputs into public aggregate digest
    signal accum[N];
    accum[0] <== y[0];
    for (var i = 1; i < N; i++) {
        accum[i] <== accum[i - 1] + y[i];
    }

    aggregateDigest <== accum[N - 1];
}

// 4-slot vector matching client CKKS vector [10.5, 20.5, 30.5, 40.5] scaled to integer field
component main {public [bias]} = VectorPolyEval(4);

