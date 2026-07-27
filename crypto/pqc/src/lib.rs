use rand_core::OsRng;
use sha2::Sha256;
use hkdf::Hkdf;
use x25519_dalek::{StaticSecret, PublicKey};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3::exceptions::PyValueError;

pub struct HybridHandshakeOutput {
    pub kyber_ciphertext: Vec<u8>,
    pub x25519_ephemeral_pk: Vec<u8>,
    pub shared_secret: Vec<u8>,
}

pub fn perform_hybrid_kex(
    client_kyber_pk: &[u8],
    client_x25519_pk: &[u8],
) -> Result<HybridHandshakeOutput, &'static str> {
    let (kyber_ct, kyber_ss) = pqc_kyber::encapsulate(client_kyber_pk, &mut OsRng)
        .map_err(|_| "Failed to perform Kyber encapsulation. Invalid public key?")?;

    let worker_x25519_sk = StaticSecret::random_from_rng(OsRng);
    let worker_x25519_pk = PublicKey::from(&worker_x25519_sk);
    
    let mut client_x25519_pk_bytes = [0u8; 32];
    if client_x25519_pk.len() != 32 {
        return Err("Invalid X25519 public key length.");
    }
    client_x25519_pk_bytes.copy_from_slice(client_x25519_pk);
    let client_x25519_pk_obj = PublicKey::from(client_x25519_pk_bytes);
    
    let x25519_ss = worker_x25519_sk.diffie_hellman(&client_x25519_pk_obj);

    let mut combined_input = Vec::new();
    combined_input.extend_from_slice(&kyber_ss);
    combined_input.extend_from_slice(x25519_ss.as_bytes()); 

    let hk = Hkdf::<Sha256>::new(None, &combined_input);
    let mut okm = [0u8; 64];
    hk.expand(b"session-root", &mut okm).expect("HKDF expansion failed");

    Ok(HybridHandshakeOutput {
        kyber_ciphertext: kyber_ct.to_vec(),
        x25519_ephemeral_pk: worker_x25519_pk.as_bytes().to_vec(),
        shared_secret: okm.to_vec(),
    })
}

// ==========================================
// PyO3 Python Bindings
// ==========================================

#[pyfunction]
fn generate_client_keys<'a>(py: Python<'a>) -> PyResult<(Bound<'a, PyBytes>, Bound<'a, PyBytes>, Bound<'a, PyBytes>, Bound<'a, PyBytes>)> {
    let mut client_rng = OsRng;
    let kyber_keys = pqc_kyber::keypair(&mut client_rng).map_err(|_| PyValueError::new_err("Kyber keygen failed"))?;
    
    let x25519_sk = StaticSecret::random_from_rng(OsRng);
    let x25519_pk = PublicKey::from(&x25519_sk);

    Ok((
        PyBytes::new_bound(py, &kyber_keys.public),
        PyBytes::new_bound(py, &kyber_keys.secret),
        PyBytes::new_bound(py, x25519_pk.as_bytes()),
        PyBytes::new_bound(py, &x25519_sk.to_bytes())
    ))
}

#[pyfunction]
fn worker_encapsulate<'a>(
    py: Python<'a>, 
    client_kyber_pk: &[u8], 
    client_x25519_pk: &[u8]
) -> PyResult<(Bound<'a, PyBytes>, Bound<'a, PyBytes>)> {
    let output = perform_hybrid_kex(client_kyber_pk, client_x25519_pk)
        .map_err(|e| PyValueError::new_err(e))?;
    
    Ok((
        PyBytes::new_bound(py, &output.kyber_ciphertext),
        PyBytes::new_bound(py, &output.x25519_ephemeral_pk)
    ))
}

#[pyfunction]
fn client_decapsulate<'a>(
    py: Python<'a>,
    worker_kyber_ct: &[u8],
    worker_x25519_pk: &[u8],
    client_kyber_sk: &[u8],
    client_x25519_sk: &[u8]
) -> PyResult<Bound<'a, PyBytes>> {
    let kyber_ss = pqc_kyber::decapsulate(worker_kyber_ct, client_kyber_sk)
        .map_err(|_| PyValueError::new_err("Kyber decapsulation failed"))?;

    let mut sk_bytes = [0u8; 32];
    if client_x25519_sk.len() != 32 {
        return Err(PyValueError::new_err("Invalid X25519 SK length"));
    }
    sk_bytes.copy_from_slice(client_x25519_sk);
    let sk = StaticSecret::from(sk_bytes);

    let mut pk_bytes = [0u8; 32];
    if worker_x25519_pk.len() != 32 {
        return Err(PyValueError::new_err("Invalid X25519 PK length"));
    }
    pk_bytes.copy_from_slice(worker_x25519_pk);
    let pk = PublicKey::from(pk_bytes);

    let x25519_ss = sk.diffie_hellman(&pk);

    let mut combined_input = Vec::new();
    combined_input.extend_from_slice(&kyber_ss);
    combined_input.extend_from_slice(x25519_ss.as_bytes());

    let hk = Hkdf::<Sha256>::new(None, &combined_input);
    let mut okm = [0u8; 64];
    hk.expand(b"session-root", &mut okm).map_err(|_| PyValueError::new_err("HKDF failed"))?;

    Ok(PyBytes::new_bound(py, &okm))
}

// ==========================================
// ML-DSA PyO3 Bindings
// ==========================================

#[pyfunction]
fn generate_mldsa_keys<'a>(py: Python<'a>) -> PyResult<(Bound<'a, PyBytes>, Bound<'a, PyBytes>)> {
    use ml_dsa::{MlDsa65, Generate, SigningKey, Keypair};
    use ml_dsa::KeyExport; // For to_bytes
    
    // Generate a fresh keypair
    let signing_key = SigningKey::<MlDsa65>::generate();
    let verifying_key = signing_key.verifying_key();
    
    let sk_bytes = signing_key.to_bytes();
    let vk_bytes = verifying_key.to_bytes();
    
    Ok((
        PyBytes::new_bound(py, &vk_bytes),
        PyBytes::new_bound(py, &sk_bytes)
    ))
}

#[pyfunction]
fn sign_message<'a>(py: Python<'a>, secret_key: &[u8], message: &[u8]) -> PyResult<Bound<'a, PyBytes>> {
    use ml_dsa::{MlDsa65, SigningKey, Signer};
    use ml_dsa::SignatureEncoding; // For to_bytes on signature
    
    let seed: &ml_dsa::Seed = secret_key.try_into()
        .map_err(|_| PyValueError::new_err("Invalid ML-DSA secret key length (must be 32 bytes)"))?;
    let sk = SigningKey::<MlDsa65>::from_seed(seed);
        
    let signature = sk.sign(message);
    let sig_bytes = signature.to_bytes();
    
    Ok(PyBytes::new_bound(py, &sig_bytes))
}

#[pyfunction]
fn verify_signature(public_key: &[u8], message: &[u8], signature: &[u8]) -> PyResult<bool> {
    use ml_dsa::{MlDsa65, VerifyingKey, Verifier, Signature};
    
    // For VerifyingKey
    let vk_bytes_ref: &ml_dsa::EncodedVerifyingKey<MlDsa65> = public_key.try_into()
        .map_err(|_| PyValueError::new_err("Invalid ML-DSA public key length"))?;
    
    let vk = VerifyingKey::<MlDsa65>::decode(vk_bytes_ref);
        
    // Signature implements TryFrom<&[u8]> directly
    let sig = Signature::<MlDsa65>::try_from(signature)
        .map_err(|_| PyValueError::new_err("Invalid ML-DSA signature format"))?;
        
    match vk.verify(message, &sig) {
        Ok(_) => Ok(true),
        Err(_) => Ok(false),
    }
}

#[pymodule]
fn crypto_pqc(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_client_keys, m)?)?;
    m.add_function(wrap_pyfunction!(worker_encapsulate, m)?)?;
    m.add_function(wrap_pyfunction!(client_decapsulate, m)?)?;
    
    // ML-DSA exports
    m.add_function(wrap_pyfunction!(generate_mldsa_keys, m)?)?;
    m.add_function(wrap_pyfunction!(sign_message, m)?)?;
    m.add_function(wrap_pyfunction!(verify_signature, m)?)?;
    Ok(())
}
