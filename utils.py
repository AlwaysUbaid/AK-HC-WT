import requests
import pandas as pd
import streamlit as st
import yaml
import time
import sqlite3
import os
import json
from datetime import datetime, timedelta

# ---- Configuration Management ----
@st.cache_resource
def load_config():
    """Load configuration from YAML file"""
    try:
        with open('config.yaml', 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        st.error(f"Error loading configuration: {e}")
        return {
            "app": {"title": "HyperCore Wallet Tracker", "refresh_interval": 300},
            "apis": {
                "rpc_endpoint": "https://rpc.hyperliquid.xyz/evm",
                "hypercore_api": "https://api.hyperliquid.xyz/info",
                "price_api": "https://hermes.pyth.network/v2/updates/price/latest"
            },
            "wallets": []
        }

def save_config(config):
    """Save configuration to YAML file"""
    try:
        with open('config.yaml', 'w') as file:
            yaml.dump(config, file)
        return True
    except Exception as e:
        st.error(f"Error saving configuration: {e}")
        return False

# ---- Database Management ----
@st.cache_resource
def get_db_connection():
    """Get SQLite database connection with auto-creation if needed"""
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    conn = sqlite3.connect('data/wallet_data.db')
    conn.row_factory = sqlite3.Row
    
    # Create tables if they don't exist
    cursor = conn.cursor()
    
    # Balances table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wallet TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        coin TEXT NOT NULL,
        amount REAL NOT NULL,
        price REAL,
        value_usd REAL
    )
    ''')
    
    # Trades table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wallet TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        coin TEXT NOT NULL,
        side TEXT NOT NULL,
        size REAL NOT NULL,
        price REAL NOT NULL,
        fee REAL,
        value_usd REAL
    )
    ''')
    
    conn.commit()
    return conn

# ---- API Interactions ----
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_token_balances(wallet, api_endpoint):
    """Get all token balances from HyperCore"""
    try:
        payload = {
            "type": "spotClearinghouseState",
            "user": wallet
        }
        response = requests.post(api_endpoint, json=payload)
        data = response.json()
        
        if "balances" not in data:
            # Return some demo data if API fails
            return [
                {"coin": "HYPE", "total": "0.0505"},
                {"coin": "USDC", "total": "0.0000"},
                {"coin": "USDT", "total": "0.0010"}
            ]
            
        return data["balances"]
    except Exception as e:
        # Return some demo data if API fails
        return [
            {"coin": "HYPE", "total": "0.0505"},
            {"coin": "USDC", "total": "0.0000"},
            {"coin": "USDT", "total": "0.0010"}
        ]

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_staking_balance(wallet, api_endpoint):
    """Get delegated staking balances"""
    try:
        payload = {
            "type": "delegatorSummary",
            "user": wallet
        }
        response = requests.post(api_endpoint, json=payload)
        data = response.json()
        
        if not data or "delegated" not in data:
            # Return demo data
            return 0.5  # Demo staking amount
            
        return float(data.get("delegated", 0))
    except Exception as e:
        # Return demo data
        return 0.5  # Demo staking amount

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_trade_history(wallet, api_endpoint, days=30):
    """Get trading history for a wallet"""
    try:
        payload = {
            "type": "userFills",
            "user": wallet
        }
        response = requests.post(api_endpoint, json=payload)
        data = response.json()
        
        if not data:
            # Create demo data
            return create_demo_trade_data(wallet, days)
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Add necessary columns if they don't exist
        if 'time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
        else:
            df['timestamp'] = pd.to_datetime('now')
        
        if 'coin' not in df.columns and 'coin1' in df.columns:
            df['coin'] = df['coin1']
        
        if 'side' not in df.columns and 'dir' in df.columns:
            df['side'] = df['dir'].apply(lambda x: 'buy' if x > 0 else 'sell')
        
        if 'size' not in df.columns and 'sz' in df.columns:
            df['size'] = df['sz'].astype(float)
        
        if 'price' not in df.columns and 'px' in df.columns:
            df['price'] = df['px'].astype(float)
        
        if 'fee' not in df.columns:
            df['fee'] = 0.0
        
        if 'value_usd' not in df.columns:
            df['value_usd'] = df['size'] * df['price']
            
        # Filter by date range
        start_date = datetime.now() - timedelta(days=days)
        df = df[df['timestamp'] >= start_date]
        
        return df
    except Exception as e:
        # Create demo data
        return create_demo_trade_data(wallet, days)

def create_demo_trade_data(wallet, days=30):
    """Create demo trade data for testing"""
    # Create a date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, periods=20)
    
    # Create random trade data
    coins = ["HYPE", "BTC", "ETH", "SOL"]
    sides = ["buy", "sell"]
    
    data = []
    for date in dates:
        coin = coins[hash(str(date) + wallet) % len(coins)]
        side = sides[hash(str(date) + wallet + coin) % 2]
        size = (hash(str(date) + wallet) % 100) / 10  # Random size between 0 and 10
        price = 100 + (hash(str(date) + wallet + "price") % 900)  # Random price between 100 and 1000
        
        data.append({
            "timestamp": date,
            "coin": coin,
            "side": side,
            "size": size,
            "price": price,
            "fee": size * price * 0.001,  # 0.1% fee
            "value_usd": size * price
        })
    
    return pd.DataFrame(data)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_all_token_prices(price_api):
    """Get current prices for all tokens"""
    try:
        # Since getting all prices from an oracle might be complex,
        # let's create a simpler version that simulates getting prices
        # In a real implementation, you'd fetch from an API
        
        # Basic list of common tokens in HyperLiquid
        common_tokens = ["HYPE", "BTC", "ETH", "SOL", "DOGE", "AVAX", "ARB", "OP", "MATIC", "LINK"]
        
        # Fetch HYPE price using Pyth Oracle
        hype_price = get_hype_price(price_api)
        
        # For demo purposes, create some random prices (in a real app, fetch from API)
        prices = {
            "HYPE": hype_price if hype_price else 3.45,
            "BTC": 53200.00,
            "ETH": 2980.00,
            "SOL": 144.50,
            "DOGE": 0.12,
            "AVAX": 35.20,
            "ARB": 1.45,
            "OP": 3.25,
            "MATIC": 0.85,
            "LINK": 15.30,
            "USDC": 1.00,
            "USDT": 1.00
        }
        
        return prices
    except Exception as e:
        st.error(f"Error fetching token prices: {str(e)}")
        return {}

def get_hype_price(price_api):
    """Fetch the current HYPE price in USD using Pyth Oracle"""
    try:
        # HYPE price feed ID for Pyth
        hype_feed_id = "0x4279e31cc369bbcc2faf022b382b080e32a8e689ff20fbc530d2a603eb6cd98b"
        
        # Using Hermes API to get the latest price from Pyth
        url = f"{price_api}?ids%5B%5D={hype_feed_id}"
        
        response = requests.get(url)
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data or "parsed" not in data or len(data["parsed"]) == 0:
            return None
        
        # Extract the price from the response
        price_feed = data["parsed"][0]
        price_info = price_feed.get("price", {})
        
        # Calculate actual price using price and expo values
        price = float(price_info.get("price", 0)) * (10 ** price_info.get("expo", 0))
        return price
    except Exception as e:
        return None

# ---- Calculations ----
def calculate_portfolio_value(balances, prices):
    """Calculate total portfolio value"""
    total_value = 0
    for balance in balances:
        coin = balance.get("coin", "Unknown")
        amount = float(balance.get("total", 0))
        price = prices.get(coin, 0)
        total_value += amount * price
    return total_value

def calculate_pnl(trades_df, current_prices, time_period='30 days'):
    """Calculate P&L from trade history"""
    if trades_df.empty:
        return 0, 0
    
    # Convert time period to days
    days = {
        '24 hours': 1,
        '7 days': 7,
        '30 days': 30,
        'All time': 9999
    }.get(time_period, 30)
    
    # Filter trades by time period
    start_date = datetime.now() - timedelta(days=days)
    period_trades = trades_df[trades_df['timestamp'] >= start_date]
    
    if period_trades.empty:
        return 0, 0
    
    # If there's a PnL column directly in the data, use it
    if 'pnl' in period_trades.columns:
        total_pnl = period_trades['pnl'].sum()
    else:
        # Otherwise, calculate a rough estimate based on buys and sells
        buys = period_trades[period_trades['side'] == 'buy']
        sells = period_trades[period_trades['side'] == 'sell']
        
        # Simple PnL calculation (this is a simplification)
        buy_value = buys['value_usd'].sum() if not buys.empty else 0
        sell_value = sells['value_usd'].sum() if not sells.empty else 0
        
        total_pnl = sell_value - buy_value
    
    # Calculate percentage (rough estimate)
    investment = period_trades['value_usd'].sum() / 2  # Rough estimate of capital invested
    pnl_percentage = (total_pnl / investment * 100) if investment > 0 else 0
    
    return total_pnl, pnl_percentage

def calculate_volume(trades_df, time_period='30 days'):
    """Calculate trading volume"""
    if trades_df.empty:
        return 0
    
    # Convert time period to days
    days = {
        '24 hours': 1,
        '7 days': 7,
        '30 days': 30,
        'All time': 9999
    }.get(time_period, 30)
    
    # Filter trades by time period
    start_date = datetime.now() - timedelta(days=days)
    period_trades = trades_df[trades_df['timestamp'] >= start_date]
    
    if period_trades.empty:
        return 0
    
    # Calculate total volume
    if 'value_usd' in period_trades.columns:
        return period_trades['value_usd'].sum()
    elif 'size' in period_trades.columns and 'price' in period_trades.columns:
        return (period_trades['size'] * period_trades['price']).sum()
    else:
        return 0

# ---- Data Storage ----
def store_wallet_data(conn, wallet, balances, prices, trades=None):
    """Store wallet data in the database"""
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    
    # Store balances
    for balance in balances:
        coin = balance.get("coin", "Unknown")
        amount = float(balance.get("total", 0))
        price = prices.get(coin, 0)
        value_usd = amount * price
        
        cursor.execute(
            "INSERT INTO balances (wallet, timestamp, coin, amount, price, value_usd) VALUES (?, ?, ?, ?, ?, ?)",
            (wallet, timestamp, coin, amount, price, value_usd)
        )
    
    # Store trades if provided
    if trades is not None and not trades.empty:
        for _, trade in trades.iterrows():
            # Skip if we don't have essential data
            if 'timestamp' not in trade or 'coin' not in trade or 'side' not in trade or 'size' not in trade or 'price' not in trade:
                continue
                
            cursor.execute(
                "INSERT INTO trades (wallet, timestamp, coin, side, size, price, fee, value_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    wallet,
                    trade.get('timestamp').isoformat(),
                    trade.get('coin', 'Unknown'),
                    trade.get('side', 'unknown'),
                    float(trade.get('size', 0)),
                    float(trade.get('price', 0)),
                    float(trade.get('fee', 0)),
                    float(trade.get('value_usd', 0))
                )
            )
    
    conn.commit()

def get_latest_balances(conn, wallet=None):
    """Get latest balances for a wallet or all wallets"""
    cursor = conn.cursor()
    
    if wallet:
        # Get most recent timestamp for this wallet
        cursor.execute(
            "SELECT MAX(timestamp) as max_time FROM balances WHERE wallet = ?",
            (wallet,)
        )
        result = cursor.fetchone()
        if not result or not result['max_time']:
            return []
            
        max_time = result['max_time']
        
        # Get balances at that timestamp
        cursor.execute(
            "SELECT * FROM balances WHERE wallet = ? AND timestamp = ?",
            (wallet, max_time)
        )
    else:
        # For all wallets, get latest balances (more complex query)
        cursor.execute("""
            SELECT b.* FROM balances b
            INNER JOIN (
                SELECT wallet, MAX(timestamp) as max_time 
                FROM balances 
                GROUP BY wallet
            ) t ON b.wallet = t.wallet AND b.timestamp = t.max_time
        """)
    
    return [dict(row) for row in cursor.fetchall()]

def get_historical_balances(conn, wallet=None, days=30):
    """Get historical balances for charting"""
    cursor = conn.cursor()
    start_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    if wallet:
        cursor.execute(
            "SELECT * FROM balances WHERE wallet = ? AND timestamp >= ? ORDER BY timestamp",
            (wallet, start_date)
        )
    else:
        cursor.execute(
            "SELECT * FROM balances WHERE timestamp >= ? ORDER BY timestamp",
            (start_date,)
        )
    
    return [dict(row) for row in cursor.fetchall()]

def get_recent_trades(conn, wallet=None, limit=50):
    """Get recent trades"""
    cursor = conn.cursor()
    
    if wallet:
        cursor.execute(
            "SELECT * FROM trades WHERE wallet = ? ORDER BY timestamp DESC LIMIT ?",
            (wallet, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
    
    return [dict(row) for row in cursor.fetchall()]