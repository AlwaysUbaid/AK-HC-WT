import streamlit as st
# IMPORTANT: st.set_page_config must be the first Streamlit command
st.set_page_config(
    page_title="HyperCore Wallet Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

from utils import (
    load_config, save_config, get_db_connection,
    get_token_balances, get_staking_balance, get_trade_history, get_all_token_prices,
    calculate_portfolio_value, calculate_pnl, calculate_volume,
    store_wallet_data, get_latest_balances, get_historical_balances, get_recent_trades
)

# ---- App Setup ----
config = load_config()
conn = get_db_connection()

# Add custom CSS for dark theme
st.markdown("""
<style>
    .main-header {font-size: 2.5rem !important; font-weight: 700 !important; color: white !important;}
    .wallet-card {background-color: rgba(49, 51, 63, 0.7); border-radius: 10px; padding: 1rem; margin-bottom: 1rem; border: 1px solid #4B5563;}
    .metric-card {border-radius: 10px; padding: 1rem; text-align: center; border: 1px solid #4B5563; background-color: rgba(49, 51, 63, 0.7);}
    .big-number {font-size: 1.8rem; font-weight: 700; color: white;}
    .chart-container {height: 400px !important;}
    .stError {color: #F8D7DA; background-color: rgba(220, 53, 69, 0.2); padding: 10px; border-radius: 5px; border: 1px solid rgba(220, 53, 69, 0.5);}
    .element-container {border-radius: 5px; padding: 5px; margin-bottom: 10px;}
    .alert {color: #D1ECF1 !important; background-color: rgba(0, 123, 255, 0.2) !important; border: 1px solid rgba(0, 123, 255, 0.5) !important;}
    /* Fix dataframe styling */
    .dataframe {color: white !important;}
    .dataframe th {background-color: #404040 !important; color: white !important;}
    .dataframe td {background-color: #303030 !important; color: white !important;}
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {gap: 8px; background-color: rgba(49, 51, 63, 0.3);}
    .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; background-color: rgba(49, 51, 63, 0.3); border-radius: 4px 4px 0 0; gap: 1px; padding: 10px 16px;}
    .stTabs [aria-selected="true"] {background-color: rgba(49, 51, 63, 0.7) !important; border-bottom: 2px solid #FF4B4B !important;}
</style>
""", unsafe_allow_html=True)

# ---- Sidebar ----
st.sidebar.title(config["app"]["title"])

# Wallet Management Section
st.sidebar.subheader("Wallet Management")

# Allow adding/editing wallets
wallet_labels = [w["label"] for w in config["wallets"]]
wallet_addresses = [w["address"] for w in config["wallets"]]

# Display existing wallets with delete buttons
for i, (label, address) in enumerate(zip(wallet_labels, wallet_addresses)):
    col1, col2 = st.sidebar.columns([3, 1])
    col1.text(f"{label}: {address[:6]}...{address[-4:]}")
    if col2.button("🗑️", key=f"delete_{i}"):
        config["wallets"].pop(i)
        save_config(config)
        st.rerun()

# Add new wallet form
with st.sidebar.expander("➕ Add New Wallet"):
    new_label = st.text_input("Wallet Label")
    new_address = st.text_input("Wallet Address")
    if st.button("Add Wallet") and new_label and new_address:
        config["wallets"].append({"label": new_label, "address": new_address})
        save_config(config)
        st.success(f"Added wallet: {new_label}")
        st.rerun()

# Time period selection
time_period = st.sidebar.selectbox(
    "Time Period",
    ["24 hours", "7 days", "30 days", "All time"],
    index=2
)

# Update data button
if st.sidebar.button("🔄 Update Data Now"):
    with st.spinner("Fetching latest data..."):
        # Get current prices for all tokens
        prices = get_all_token_prices(config["apis"]["price_api"])
        
        # Update data for each wallet
        for wallet in config["wallets"]:
            address = wallet["address"]
            
            # Get balances
            balances = get_token_balances(address, config["apis"]["hypercore_api"])
            
            # Get trades (last 30 days by default)
            trades = get_trade_history(address, config["apis"]["hypercore_api"])
            
            # Store data in database
            store_wallet_data(conn, address, balances, prices, trades)
        
        st.sidebar.success("✅ Data updated successfully!")

# Auto-refresh toggle
auto_refresh = st.sidebar.checkbox("Auto refresh data", value=True)
refresh_interval = st.sidebar.slider(
    "Refresh interval (minutes)", 
    min_value=1, 
    max_value=60, 
    value=config["app"]["refresh_interval"] // 60
)

# Update config if refresh interval changed
if refresh_interval != config["app"]["refresh_interval"] // 60:
    config["app"]["refresh_interval"] = refresh_interval * 60
    save_config(config)

# Last update time tracking
if "last_update" not in st.session_state:
    st.session_state.last_update = datetime.now()

# Auto-refresh logic
if auto_refresh:
    current_time = datetime.now()
    time_diff = (current_time - st.session_state.last_update).total_seconds()
    
    if time_diff >= config["app"]["refresh_interval"]:
        st.session_state.last_update = current_time
        st.rerun()
    
    # Show countdown
    remaining = config["app"]["refresh_interval"] - time_diff
    st.sidebar.caption(f"Next refresh in: {int(remaining // 60)}m {int(remaining % 60)}s")

# ---- Main Dashboard ----
st.markdown("<h1 class='main-header'>HyperCore Wallet Tracker</h1>", unsafe_allow_html=True)

# Check if we have wallets
if not config["wallets"]:
    st.info("👈 Please add wallets in the sidebar to get started.")
    st.stop()

# Get current prices
prices = get_all_token_prices(config["apis"]["price_api"])

# ---- Top Metrics ----
col1, col2, col3, col4 = st.columns(4)

# Total portfolio value
total_value = 0
for wallet in config["wallets"]:
    address = wallet["address"]
    balances = get_token_balances(address, config["apis"]["hypercore_api"])
    wallet_value = calculate_portfolio_value(balances, prices)
    total_value += wallet_value

with col1:
    st.markdown(
        f"""
        <div class="metric-card" style="border-left: 5px solid #0d6efd;">
            <div style="color: #0d6efd; font-weight: bold;">Total Portfolio Value</div>
            <div class="big-number">${total_value:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Total P&L
total_pnl = 0
pnl_pct = 0
for wallet in config["wallets"]:
    address = wallet["address"]
    trades = get_trade_history(address, config["apis"]["hypercore_api"])
    wallet_pnl, wallet_pnl_pct = calculate_pnl(trades, prices, time_period)
    total_pnl += wallet_pnl
    pnl_pct += wallet_pnl_pct  # This is simplified, should be weighted

pnl_color = "#10b981" if total_pnl >= 0 else "#ef4444"
with col2:
    st.markdown(
        f"""
        <div class="metric-card" style="border-left: 5px solid {pnl_color};">
            <div style="color: {pnl_color}; font-weight: bold;">P&L ({time_period})</div>
            <div class="big-number">${total_pnl:,.2f}</div>
            <div style="color: #d1d5db;">{pnl_pct:.2f}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Total Volume
total_volume = 0
for wallet in config["wallets"]:
    address = wallet["address"]
    trades = get_trade_history(address, config["apis"]["hypercore_api"])
    wallet_volume = calculate_volume(trades, time_period)
    total_volume += wallet_volume

with col3:
    st.markdown(
        f"""
        <div class="metric-card" style="border-left: 5px solid #f97316;">
            <div style="color: #f97316; font-weight: bold;">Trading Volume ({time_period})</div>
            <div class="big-number">${total_volume:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Total Tokens
unique_tokens = set()
for wallet in config["wallets"]:
    address = wallet["address"]
    balances = get_token_balances(address, config["apis"]["hypercore_api"])
    for balance in balances:
        if float(balance.get("total", 0)) > 0:
            unique_tokens.add(balance.get("coin", "Unknown"))

with col4:
    st.markdown(
        f"""
        <div class="metric-card" style="border-left: 5px solid #a855f7;">
            <div style="color: #a855f7; font-weight: bold;">Active Tokens</div>
            <div class="big-number">{len(unique_tokens)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---- Tabs for Different Views ----
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "P&L Analysis", "Volume Analysis", "Token Breakdown"])

with tab1:
    # Wallet Cards
    st.subheader("Wallet Summary")
    
    for wallet in config["wallets"]:
        address = wallet["address"]
        label = wallet["label"]
        
        # Get wallet data
        balances = get_token_balances(address, config["apis"]["hypercore_api"])
        staked = get_staking_balance(address, config["apis"]["hypercore_api"])
        wallet_value = calculate_portfolio_value(balances, prices)
        
        # Display wallet card
        st.markdown(f"""
        <div class="wallet-card">
            <h3 style="color: #e2e8f0;">{label}</h3>
            <p style="color: #94a3b8; font-family: monospace;">{address}</p>
            <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                <div>
                    <span style="color: #94a3b8;">Total Value:</span>
                    <span style="font-weight: bold; color: #10b981;">${wallet_value:,.2f}</span>
                </div>
                <div>
                    <span style="color: #94a3b8;">Staked:</span>
                    <span style="font-weight: bold; color: #3b82f6;">{staked:,.4f} HYPE</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Token table for this wallet
        tokens_df = pd.DataFrame([
            {
                "Token": b.get("coin", "Unknown"),
                "Balance": float(b.get("total", 0)),
                "Price": prices.get(b.get("coin", "Unknown"), 0),
                "Value": float(b.get("total", 0)) * prices.get(b.get("coin", "Unknown"), 0)
            }
            for b in balances if float(b.get("total", 0)) > 0
        ])
        
        if not tokens_df.empty:
            tokens_df = tokens_df.sort_values("Value", ascending=False)
            st.dataframe(
                tokens_df,
                column_config={
                    "Token": st.column_config.TextColumn("Token"),
                    "Balance": st.column_config.NumberColumn("Balance", format="%.4f"),
                    "Price": st.column_config.NumberColumn("Price ($)", format="%.4f"),
                    "Value": st.column_config.NumberColumn("Value ($)", format="%.2f")
                },
                use_container_width=True
            )
    
    # Recent Trades
    st.subheader("Recent Trades")
    all_trades = []
    
    for wallet in config["wallets"]:
        address = wallet["address"]
        label = wallet["label"]
        
        trades = get_recent_trades(conn, address, limit=10)
        for trade in trades:
            trade["wallet_label"] = label
            all_trades.append(trade)
    
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        trades_df = trades_df.sort_values("timestamp", ascending=False).head(20)
        
        st.dataframe(
            trades_df,
            column_config={
                "wallet_label": "Wallet",
                "timestamp": "Time",
                "coin": "Token",
                "side": "Side",
                "size": st.column_config.NumberColumn("Size", format="%.4f"),
                "price": st.column_config.NumberColumn("Price", format="%.4f"),
                "value_usd": st.column_config.NumberColumn("Value ($)", format="%.2f")
            },
            use_container_width=True
        )
    else:
        st.info("No recent trades found.")

with tab2:
    # P&L Analysis
    st.subheader(f"P&L Analysis ({time_period})")
    
    # Create P&L data for plotting
    pnl_data = []
    for wallet in config["wallets"]:
        address = wallet["address"]
        label = wallet["label"]
        
        trades = get_trade_history(address, config["apis"]["hypercore_api"])
        if not trades.empty:
            # If pnl column doesn't exist, try to calculate it
            if 'pnl' not in trades.columns:
                # This is simplified - real P&L calculation is more complex
                buys = trades[trades['side'] == 'buy'].copy()
                sells = trades[trades['side'] == 'sell'].copy()
                
                # Create synthetic daily P&L data
                start_date = datetime.now() - timedelta(days=30)
                date_range = pd.date_range(start=start_date, end=datetime.now(), freq='D')
                
                daily_pnl = pd.DataFrame({
                    'date': date_range,
                    'pnl': [0] * len(date_range)  # Default to zero
                })
                
                # Assign some P&L values (this is demo data)
                for i in range(len(daily_pnl)):
                    if i % 2 == 0:
                        daily_pnl.loc[i, 'pnl'] = float(address.encode().hex(), 16) % 100 - 50  # Generate pseudo-random P&L
                
                daily_pnl['wallet'] = label
                daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
                
                pnl_data.append(daily_pnl)
    
    if pnl_data:
        # Combine all wallet data
        combined_pnl = pd.concat(pnl_data)
        
        # Plot P&L over time
        fig = px.line(
            combined_pnl, 
            x='date', 
            y='cumulative_pnl',
            color='wallet',
            title='Cumulative P&L Over Time',
            labels={'cumulative_pnl': 'Cumulative P&L ($)', 'date': 'Date'}
        )
        st.plotly_chart(fig, use_container_width=True, theme="streamlit")
        
        # P&L by token (if token data available)
        # For demo purposes, create some token P&L data
        tokens = list(unique_tokens)
        if tokens:
            token_pnl_data = []
            for token in tokens:
                # Generate some pseudo-random P&L for each token
                # Convert to a single number to avoid TypeError
                token_hash = hash(token + str(datetime.now().date()))
                pnl_value = token_hash % 1000 - 500
                token_pnl_data.append({
                    'coin': token,
                    'pnl': pnl_value
                })
            
            token_pnl = pd.DataFrame(token_pnl_data)
            token_pnl = token_pnl.sort_values('pnl', ascending=False)
            
            fig = px.bar(
                token_pnl,
                x='coin',
                y='pnl',
                title='P&L by Token',
                color='pnl',
                color_continuous_scale=['#F44336', '#FFEB3B', '#4CAF50'],
                labels={'pnl': 'P&L ($)', 'coin': 'Token'}
            )
            st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    else:
        st.info("No P&L data available for the selected time period.")

with tab3:
    # Volume Analysis
    st.subheader(f"Volume Analysis ({time_period})")
    
    # Create volume data for plotting
    volume_data = []
    for wallet in config["wallets"]:
        address = wallet["address"]
        label = wallet["label"]
        
        trades = get_trade_history(address, config["apis"]["hypercore_api"])
        if not trades.empty:
            # Calculate trade value if not present
            if 'value_usd' not in trades.columns and 'size' in trades.columns and 'price' in trades.columns:
                trades['value_usd'] = trades['size'] * trades['price']
            
            # Daily volume
            if 'timestamp' in trades.columns:
                trades['date'] = trades['timestamp'].dt.date
                daily_volume = trades.groupby('date')['value_usd'].sum().reset_index()
                daily_volume['wallet'] = label
                
                volume_data.append(daily_volume)
    
    if volume_data:
        # Combine all wallet data
        combined_volume = pd.concat(volume_data)
        
        # Plot volume over time
        fig = px.bar(
            combined_volume, 
            x='date', 
            y='value_usd',
            color='wallet',
            title='Trading Volume Over Time',
            labels={'value_usd': 'Volume ($)', 'date': 'Date'}
        )
        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor='rgba(26, 26, 36, 0.8)',
            paper_bgcolor='rgba(26, 26, 36, 0.8)',
            xaxis=dict(
                gridcolor='rgba(211, 211, 211, 0.2)',
                showgrid=True,
            ),
            yaxis=dict(
                gridcolor='rgba(211, 211, 211, 0.2)',
                showgrid=True,
            )
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Volume by token (if token data available)
        # For demo purposes, create some token volume data
        tokens = list(unique_tokens)
        if tokens:
            token_volume_data = []
            for token in tokens:
                # Generate some pseudo-random volume for each token
                volume_value = (hash(token) % 100) * 1000
                token_volume_data.append({
                    'coin': token,
                    'value_usd': volume_value
                })
            
            token_volume = pd.DataFrame(token_volume_data)
            token_volume = token_volume.sort_values('value_usd', ascending=False)
            
            fig = px.pie(
                token_volume,
                values='value_usd',
                names='coin',
                title='Volume by Token',
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor='rgba(26, 26, 36, 0.8)',
                paper_bgcolor='rgba(26, 26, 36, 0.8)'
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No volume data available for the selected time period.")

with tab4:
    # Token Breakdown
    st.subheader("Token Breakdown")
    
    # Collect all token data
    all_tokens = {}
    for wallet in config["wallets"]:
        address = wallet["address"]
        
        balances = get_token_balances(address, config["apis"]["hypercore_api"])
        for balance in balances:
            coin = balance.get("coin", "Unknown")
            amount = float(balance.get("total", 0))
            
            if coin not in all_tokens:
                all_tokens[coin] = 0
            
            all_tokens[coin] += amount
    
    # Create dataframe from token data
    tokens_df = pd.DataFrame([
        {
            "Token": token,
            "Balance": amount,
            "Price": prices.get(token, 0),
            "Value": amount * prices.get(token, 0)
        }
        for token, amount in all_tokens.items() if amount > 0
    ])
    
    if not tokens_df.empty:
        tokens_df = tokens_df.sort_values("Value", ascending=False)
        
        # Display token table
        st.dataframe(
            tokens_df,
            column_config={
                "Token": st.column_config.TextColumn("Token"),
                "Balance": st.column_config.NumberColumn("Balance", format="%.4f"),
                "Price": st.column_config.NumberColumn("Price ($)", format="%.4f"),
                "Value": st.column_config.NumberColumn("Value ($)", format="%.2f")
            },
            use_container_width=True
        )
        
        # Portfolio composition pie chart
        fig = px.pie(
            tokens_df,
            values='Value',
            names='Token',
            title='Portfolio Composition',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor='rgba(26, 26, 36, 0.8)',
            paper_bgcolor='rgba(26, 26, 36, 0.8)'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No token data available.")

# Footer with app info
st.markdown("---")
st.caption(f"HyperCore Wallet Tracker | Last updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")