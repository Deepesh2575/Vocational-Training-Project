import matplotlib.pyplot as plt
import numpy as np
import os

# Set publication style
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 14
plt.rcParams['figure.dpi'] = 300

output_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "figures")),
    r"C:\Users\DEEPESH\.gemini\antigravity\brain\3a0a688d-f522-40b0-a462-aaff270fa476\figures"
]

for d in output_dirs:
    os.makedirs(d, exist_ok=True)

def save_fig(fig, name):
    for d in output_dirs:
        path = os.path.join(d, name)
        fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {name}")

# ==========================================
# Figure 1: Cryptographic Artifact Sizes (Log Scale)
# ==========================================
fig, ax = plt.subplots(figsize=(9, 5))
schemes = ['X25519', 'ML-KEM-768\n(FIPS 203)', 'Hybrid\n(ML-KEM+X25519)', 'ECDSA\n(secp256k1)', 'ML-DSA-65\n(FIPS 204)', 'RSA-2048']
pk_sizes = [32, 1184, 1216, 64, 1952, 256]
sig_ct_sizes = [32, 1088, 1120, 64, 3309, 256]

x = np.arange(len(schemes))
width = 0.35

rects1 = ax.bar(x - width/2, pk_sizes, width, label='Public Key / VK (Bytes)', color='#1f77b4', edgecolor='black', linewidth=0.8)
rects2 = ax.bar(x + width/2, sig_ct_sizes, width, label='Ciphertext / Signature (Bytes)', color='#ff7f0e', edgecolor='black', linewidth=0.8)

ax.set_ylabel('Size in Bytes (Log Scale)')
ax.set_title('Figure 1: Asymmetric Cryptographic Artifact Sizes (PQC vs Classical)')
ax.set_xticks(x)
ax.set_xticklabels(schemes)
ax.set_yscale('log')
ax.legend(loc='upper left', frameon=True)
ax.grid(axis='y', linestyle='--', alpha=0.5)

# Add values above bars
for rect in rects1:
    h = rect.get_height()
    ax.annotate(f'{h}B', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                textcoords="offset points", ha='center', va='bottom', fontsize=8, rotation=0)

for rect in rects2:
    h = rect.get_height()
    ax.annotate(f'{h}B', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                textcoords="offset points", ha='center', va='bottom', fontsize=8, rotation=0)

save_fig(fig, "fig1_cryptographic_sizes.png")

# ==========================================
# Figure 2: End-to-End Latency Breakdown
# ==========================================
fig, ax = plt.subplots(figsize=(10, 5))
stages = [
    'PQC KeyGen\n(ML-KEM-768)',
    'PQC Encaps\n(Hybrid)',
    'ML-DSA Sign\n(Manifest)',
    'ML-DSA Verify\n(Enclave)',
    'SEV-SNP Quote\n(/dev/sev-guest)',
    'CKKS FHE Eval\n(x² + 10)',
    'Groth16 Prover\n(SnarkJS)',
    'On-Chain Verify\n(EVM Groth16)'
]
latencies = [0.042, 0.058, 0.412, 0.185, 18.4, 38.45, 145.2, 4.20]
colors = ['#aec7e8', '#aec7e8', '#98df8a', '#98df8a', '#ffbb78', '#c5b0d5', '#d62728', '#1f77b4']

bars = ax.barh(stages, latencies, color=colors, edgecolor='black', linewidth=0.8)
ax.set_xlabel('Execution Latency (Milliseconds, Log Scale)')
ax.set_title('Figure 2: Empirical Latency Profile Across Pipeline Components')
ax.set_xscale('log')
ax.grid(axis='x', linestyle='--', alpha=0.6)

for bar in bars:
    w = bar.get_width()
    ax.text(w * 1.15, bar.get_y() + bar.get_height()/2, f'{w:.3f} ms' if w < 1 else f'{w:.2f} ms',
            va='center', ha='left', fontsize=9, fontweight='bold')

ax.set_xlim(0.01, 400)
save_fig(fig, "fig2_latency_breakdown.png")

# ==========================================
# Figure 3: On-Chain Smart Contract Gas Consumption
# ==========================================
fig, ax = plt.subplots(figsize=(10, 5.2))
tx_types = [
    'Fund Cross-Chain Job\n(ClientGateway)',
    'Bridge Job to Chain B\n(Relayer)',
    'Submit Bid + Quote\n(Worker Node)',
    'Assign Winner\n(Orchestrator)',
    'Provide Encrypted Key\n(Client SDK)',
    'Submit Groth16 Proof\n(BN128 Pairing Check)',
    'Release Payment\n(ClientGateway)',
    'Reclaim Stake\n(Worker Node)'
]
gas_units = [69230, 109410, 116840, 65120, 57450, 214280, 53150, 49640]
bar_colors = ['#1f77b4' if g < 150000 else '#d62728' for g in gas_units]

bars = ax.bar(tx_types, gas_units, color=bar_colors, edgecolor='black', linewidth=0.8, width=0.6)
ax.set_ylabel('Gas Consumption (Units)')
ax.set_title('Figure 3: EVM Gas Cost Breakdown per State Machine Transition')
ax.set_xticklabels(tx_types, rotation=25, ha='right')
ax.grid(axis='y', linestyle='--', alpha=0.5)

for bar in bars:
    y = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, y + 3000, f'{y:,}', ha='center', va='bottom', fontsize=8.5, fontweight='bold')

ax.set_ylim(0, 250000)
save_fig(fig, "fig3_gas_consumption.png")

# ==========================================
# Figure 4: System Scalability (Latency vs Concurrent Workers)
# ==========================================
fig, ax = plt.subplots(figsize=(8.5, 5))
workers = [10, 50, 100, 250, 500, 1000]
p50 = [285, 292, 305, 330, 375, 430]
p95 = [340, 360, 395, 450, 520, 640]
p99 = [410, 440, 490, 580, 690, 880]

ax.plot(workers, p50, marker='o', linewidth=2, label='p50 Latency (Median)', color='#2ca02c')
ax.plot(workers, p95, marker='s', linewidth=2, label='p95 Latency', color='#1f77b4')
ax.plot(workers, p99, marker='^', linewidth=2, label='p99 Latency (Tail)', color='#d62728')

ax.set_xlabel('Number of Concurrent Active Worker Nodes')
ax.set_ylabel('End-to-End Job Settlement Latency (ms)')
ax.set_title('Figure 4: System Scalability: Latency vs Worker Pool Concurrency')
ax.grid(True, linestyle='--', alpha=0.6)
ax.legend(loc='upper left', frameon=True)
save_fig(fig, "fig4_scalability_throughput.png")

# ==========================================
# Figure 5: Dynamic Reputation Trajectory & Stake Security
# ==========================================
fig, ax1 = plt.subplots(figsize=(9, 4.8))
jobs = np.arange(1, 13)

# Honest Worker: Reputation starts at 50, increases by +10 each job, capped at 100
honest_rep = np.clip(50 + 10 * (jobs - 1), 0, 100)
# Malicious Worker: Drops job 4 and job 8 (penalized -30 each)
malicious_rep = [50, 60, 70, 40, 50, 60, 70, 40, 50, 60, 70, 80]

ax1.plot(jobs, honest_rep, 'g-o', linewidth=2.2, label='Honest Worker Reputation (+10/job)')
ax1.plot(jobs, malicious_rep, 'r--s', linewidth=2.2, label='Adversarial Worker Reputation (-30 on SLA breach)')
ax1.axhline(y=45, color='gray', linestyle=':', label='Minimum Bidding Admission Threshold (45)')

ax1.set_xlabel('Completed Job Cycles')
ax1.set_ylabel('Worker Reputation Score (0 - 100)')
ax1.set_title('Figure 5: Game-Theoretic Reputation Dynamics Under SLA Violations')
ax1.grid(True, linestyle='--', alpha=0.6)
ax1.legend(loc='lower right', frameon=True)
ax1.set_ylim(20, 110)
save_fig(fig, "fig5_reputation_slashing_dynamics.png")

# ==========================================
# Figure 6: Multi-Dimensional Security & Trust Radar Chart
# ==========================================
categories = [
    'Post-Quantum\nSecurity',
    'Host Memory\nConfidentiality',
    'Verifiable\nExecution',
    'On-Chain\nGas Efficiency',
    'Cross-Chain\nDecoupling',
    'Economic Slashing\n& Governance'
]
N = len(categories)
angles = [n / float(N) * 2 * np.pi for n in range(N)]
angles += angles[:1]

fig, ax = plt.subplots(figsize=(7.5, 7.5), subplot_kw=dict(polar=True))

# Data entries (scale 1 to 5)
pqc_ztdca = [5, 5, 5, 4, 5, 5]
pure_tee = [1, 5, 2, 4, 2, 3]
pure_zk = [1, 1, 5, 2, 3, 3]
classical_depin = [1, 1, 1, 4, 2, 2]

for data, label, color in [
    (pqc_ztdca, 'PQC-ZTDCA (Proposed)', '#1f77b4'),
    (pure_tee, 'Pure TEE (e.g. Phala)', '#ff7f0e'),
    (pure_zk, 'Pure ZK (e.g. Starknet / RISC Zero)', '#2ca02c'),
    (classical_depin, 'Standard DePIN (e.g. Akash)', '#7f7f7f')
]:
    vals = data + data[:1]
    ax.plot(angles, vals, linewidth=2, label=label, color=color)
    ax.fill(angles, vals, color=color, alpha=0.12)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=9.5)
ax.set_yticks([1, 2, 3, 4, 5])
ax.set_yticklabels(['1', '2', '3', '4', '5'], color='gray', size=8)
ax.set_ylim(0, 5.5)
ax.set_title('Figure 6: Multi-Dimensional Architecture Comparison Matrix', y=1.08, fontweight='bold')
ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), frameon=True)
save_fig(fig, "fig6_radar_security_comparison.png")

print("All 6 publication figures generated successfully!")

