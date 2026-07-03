# Risk Management & Position Sizing

The trading system employs strict capital preservation rules and quantitative risk constraints to prevent ruin and manage drawdowns.

---

## 📐 Kelly Criterion Position Sizing

The Risk Management Agent calculates the optimal allocation fraction of the portfolio's total equity using the Kelly Criterion:

$$f^* = \frac{p \cdot b - q}{b}$$

For binary outcome contracts (like Polymarket shares where winning pays $1.00 and losing pays $0.00), the net odds are $b = \frac{1}{\text{Price}} - 1$, and $q = 1 - p$. The formula simplifies to:

$$f^* = \frac{p - \text{Price}}{1 - \text{Price}}$$

where:
- $p$ is the model's calibrated probability of the outcome succeeding (YES or NO).
- $\text{Price}$ is the purchase price of the contract (market implied probability).

### 🛡️ Fractional Kelly Scaling
To mitigate the high volatility of full Kelly sizing (which can lead to large drawdowns due to model uncertainty), we apply a **Fractional Kelly** scaling factor (default: **25% or Quarter Kelly**):

$$f_{\text{allocated}} = 0.25 \cdot f^*$$

---

## 🚫 Portfolio Risk Shields

Before any order is approved, the Risk Management Agent verifies three primary safety constraints:

### 1. Maximum Exposure Per Trade
No single contract can exceed **10% of total portfolio equity** to prevent single-event ruin:
$$f_{\text{allocated}} \le 10\%$$

### 2. Daily Loss Limit (Trading Halt)
If the portfolio's realized or unrealized loss on a calendar day exceeds **5% of the starting portfolio equity**, the system activates a **trading halt**. All new trading is blocked, and open positions are monitored but not increased:
$$\text{Daily PnL} \le -0.05 \cdot \text{Portfolio Value}$$

### 3. Maximum Aggregate Portfolio Exposure
To maintain cash liquidity and allow room for hedging, the total aggregate exposure of all open positions combined is restricted to **90% of the portfolio value**.

---

## 📊 Value at Risk (VaR)

Value at Risk is estimated at a **95% confidence level** assuming daily weather market volatility ($\sigma \approx 15\%$):

$$\text{VaR}_{95\%} = \text{Total Exposure} \cdot \sigma \cdot 1.645$$

This represents the maximum dollar loss the portfolio is expected to experience over a 1-day horizon with 95% confidence.
