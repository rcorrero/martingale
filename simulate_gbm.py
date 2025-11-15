import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from scipy.stats import multivariate_normal

# Simulation parameters
n_realizations = 256
n_steps = 10 * 60 
dt = 1.0  # time step (seconds)
# initial_price = 100.0

# # Drift and volatility sampling (as in Asset.create_new_asset)
# def sample_drift(volatility):
#     drift = np.random.normal(0.0, 0.005)
#     # Clip drift to [-volatility, volatility]
#     return np.clip(drift, -volatility, volatility)

# def sample_volatility():
#     return np.random.uniform(0.001, 0.20)

def sample_parameters(mu_0 = 0.0, log_sigma_0 = np.log(0.05), cov=None):
    if cov is None:
        cov = np.array([
            [0.001**2, 0.0],
            [0.0, 0.5**2]
        ])
    mu, log_sigma = np.random.multivariate_normal([mu_0, log_sigma_0], cov)
    sigma = np.exp(log_sigma)
    return mu, sigma

# Prior parameters
mu_0 = -0.001
log_sigma_0 = np.log(0.05)
cov = np.array([
    [0.001**2, 0.00],
    [0.00, 0.5**2]
])

# Simulate and plot


# --- Simulation loop ---
mus = []
all_prices = []
initial_values = []
terminal_values = []
for i in range(n_realizations):
    mu, sigma = sample_parameters(mu_0, log_sigma_0, cov)
    mus.append(mu)
    mean_init = 100.0
    sigma_logn = 1.0  # Reasonable spread
    mu_logn = np.log(mean_init) - (sigma_logn**2) / 2
    initial_price = np.random.lognormal(mean=mu_logn, sigma=sigma_logn)
    initial_values.append(initial_price)
    prices = [initial_price]
    for t in range(1, n_steps):
        z = np.random.standard_normal()
        log_return = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z
        new_price = prices[-1] * np.exp(log_return)
        prices.append(new_price)
    all_prices.append(prices)
    terminal_values.append(prices[-1])

# Convert lists to numpy arrays after simulation loop
mus = np.array(mus)
all_prices = np.array(all_prices)
initial_values = np.array(initial_values)
terminal_values = np.array(terminal_values)
neg_idx = mus < 0
pos_idx = mus >= 0

norm = Normalize(vmin=mus.min(), vmax=mus.max())
cmap = plt.get_cmap('coolwarm')
fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

# Negative drift
ax = axes[0]
for prices, mu in zip(all_prices[neg_idx], mus[neg_idx]):
    ax.plot(prices, color=cmap(norm(mu)), label=f"μ={mu:.4f}")
if np.any(neg_idx):
    avg_neg = np.mean(all_prices[neg_idx], axis=0)
    ax.plot(avg_neg, color='black', linewidth=2.5, label='Average')
    avg_init_neg = np.mean(initial_values[neg_idx])
    avg_term_neg = np.mean(terminal_values[neg_idx])
    ax.set_title(f'Negative Drift (μ < 0)\nAvg init: {avg_init_neg:.2f}, Avg term: {avg_term_neg:.2f}')
else:
    ax.set_title('Negative Drift (μ < 0)\nNo series')
ax.set_xlabel('Time Step')
ax.set_ylabel('Price')
ax.grid(True)
sm_neg = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm_neg.set_array([])
fig.colorbar(sm_neg, label='Drift (μ)', ax=ax)

# Positive drift
ax = axes[1]
for prices, mu in zip(all_prices[pos_idx], mus[pos_idx]):
    ax.plot(prices, color=cmap(norm(mu)), label=f"μ={mu:.4f}")
if np.any(pos_idx):
    avg_pos = np.mean(all_prices[pos_idx], axis=0)
    ax.plot(avg_pos, color='black', linewidth=2.5, label='Average')
    avg_init_pos = np.mean(initial_values[pos_idx])
    avg_term_pos = np.mean(terminal_values[pos_idx])
    ax.set_title(f'Positive Drift (μ ≥ 0)\nAvg init: {avg_init_pos:.2f}, Avg term: {avg_term_pos:.2f}')
else:
    ax.set_title('Positive Drift (μ ≥ 0)\nNo series')
ax.set_xlabel('Time Step')
ax.grid(True)
sm_pos = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm_pos.set_array([])
fig.colorbar(sm_pos, label='Drift (μ)', ax=ax)

fig.suptitle("Sample Realizations of Geometric Brownian Motion Price Process")
plt.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.show()

# for prices, mu in zip(all_prices, mus):
#     if mu >= 0:  # Only plot positive drift realizations
#         plt.plot(prices, color=cmap(norm(mu)), label=f"μ={mu:.4f}")

# avg_initial = np.mean(initial_values)
# median_initial = np.median(initial_values)
# avg_terminal = np.mean(terminal_values)
# median_terminal = np.median(terminal_values)
# sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
# sm.set_array([])
# plt.colorbar(sm, label='Drift (μ)', ax=plt.gca())
# plt.title(
#     f"Sample Realizations of Geometric Brownian Motion Price Process\nAverage initial value: {avg_initial:.2f}, Median initial value: {median_initial:.2f}\nAverage terminal value: {avg_terminal:.2f}, Median terminal value: {median_terminal:.2f}"
# )
# plt.xlabel("Time Step")
# plt.ylabel("Price")
# # plt.yscale('log')
# plt.grid(True)
# # plt.legend(fontsize='small', loc='upper left')
# plt.tight_layout()
# plt.show()

# Grid for plotting
mu_range = np.linspace(-0.003, 0.003, 200)
log_sigma_range = np.linspace(np.log(0.001), np.log(0.2), 200)
MU, LOGSIGMA = np.meshgrid(mu_range, log_sigma_range)
pos = np.dstack((MU, LOGSIGMA))

# Bivariate normal density
rv = multivariate_normal([mu_0, log_sigma_0], cov)
Z = rv.pdf(pos)

# Plot
plt.figure(figsize=(8, 6))
plt.contourf(MU, np.exp(LOGSIGMA), Z, levels=50, cmap='viridis')
plt.xlabel('Drift (μ)')
plt.ylabel('Volatility (σ)')
plt.title('Density of Bivariate Normal Prior for (μ, log σ)')
plt.yscale('log')
plt.colorbar(label='Density')
plt.tight_layout()
plt.show()