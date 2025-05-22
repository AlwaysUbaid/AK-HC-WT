# HyperCore Wallet Tracker

A streamlined dashboard for tracking HyperLiquid wallets, built with Streamlit. Monitor token balances, P&L, trading volume, and more for multiple wallets.

## Features

- **Multi-wallet tracking**: Monitor multiple HyperLiquid wallets simultaneously
- **All tokens supported**: Track all tokens in HyperCore wallets, not just HYPE
- **P&L analysis**: View profit/loss over different time periods
- **Volume tracking**: Analyze trading volume by wallet and token
- **Portfolio overview**: See the total value and breakdown of your crypto assets
- **Auto-refresh**: Automatically update data at configurable intervals
- **Staking positions**: Track delegated staking positions

## Quick Start

### 1. Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/hyperliquid-tracker.git
cd hyperliquid-tracker

# Install dependencies
pip install -r requirements.txt

# Edit config.yaml with your wallet addresses

# Run the application
streamlit run app.py
```

### 2. Docker

```bash
# Build the Docker image
docker build -t hyperliquid-tracker .

# Run the container
docker run -p 8501:8501 -v $(pwd)/config.yaml:/app/config.yaml -v $(pwd)/data:/app/data hyperliquid-tracker
```

### 3. Deployment to Render

1. Fork this repository to your GitHub account
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Use the following settings:
   - **Environment**: Docker
   - **Build Command**: (leave empty, using Dockerfile)
   - **Start Command**: (leave empty, using Dockerfile)

## Configuration

Edit the `config.yaml` file to customize your settings:

```yaml
app:
  title: "HyperCore Wallet Tracker"
  refresh_interval: 300  # in seconds

apis:
  rpc_endpoint: "https://rpc.hyperliquid.xyz/evm"
  hypercore_api: "https://api.hyperliquid.xyz/info"
  price_api: "https://hermes.pyth.network/v2/updates/price/latest"

wallets:
  - label: "Main Account"
    address: "0xYourWalletAddress1"
  - label: "Trading Account"
    address: "0xYourWalletAddress2"
```

## License

MIT

## Acknowledgements

Built with:
- Streamlit
- Pandas
- Plotly
- HyperLiquid API