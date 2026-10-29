import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go


def get_stock_data(ticker, period="5y"):
    stock = yf.Ticker(ticker)
    data = stock.history(period=period, auto_adjust=False)
    if data.empty:
        raise ValueError(f"No data returned for ticker: {ticker}")
    return data


def calculate_moving_averages(data):
    data = data.copy()
    data['MA50'] = data['Close'].rolling(window=50).mean()
    data['MA200'] = data['Close'].rolling(window=200).mean()
    return data


def identify_golden_cross(data):
    data = data.copy()
    data['GoldenCross'] = (
        (data['MA50'] > data['MA200']) &
        (data['MA50'].shift(1) <= data['MA200'].shift(1))
    )
    return data


def implement_strategy(data):
    positions = []
    strategy_data = data.copy().dropna(subset=['MA50', 'MA200']).iloc[200:].copy()
    buy_dates = strategy_data[strategy_data['GoldenCross'] == True].index.tolist()

    for buy_date in buy_dates:
        buy_price = strategy_data.loc[buy_date, 'Close']
        target_price = buy_price * 1.15
        max_sell_date = buy_date + pd.Timedelta(days=60)
        sell_period = strategy_data.loc[buy_date:max_sell_date].copy()
        target_reached = sell_period[sell_period['Close'] >= target_price]

        if not target_reached.empty:
            sell_date = target_reached.index[0]
            sell_price = target_reached.loc[sell_date, 'Close']
            sell_reason = 'Target reached'
        else:
            sell_date_candidates = sell_period.index.tolist()
            if not sell_date_candidates:
                continue
            sell_date = sell_date_candidates[-1]
            sell_price = strategy_data.loc[sell_date, 'Close']
            sell_reason = 'Max holding period'

        holding_days = (sell_date - buy_date).days
        profit_pct = (sell_price / buy_price - 1) * 100

        positions.append({
            'BuyDate': buy_date,
            'BuyPrice': buy_price,
            'SellDate': sell_date,
            'SellPrice': sell_price,
            'HoldingDays': holding_days,
            'ProfitPct': profit_pct,
            'SellReason': sell_reason,
        })

    return pd.DataFrame(positions)


def build_strategy_data():
    data = get_stock_data('MSFT')
    data = calculate_moving_averages(data)
    data = identify_golden_cross(data)
    positions = implement_strategy(data)
    return data, positions


def compute_stats(positions):
    if positions.empty:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'average_profit': 0.0,
            'average_holding_days': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0,
        }

    total_trades = len(positions)
    win_trades = int((positions['ProfitPct'] > 0).sum())
    loss_trades = total_trades - win_trades
    win_rate = (win_trades / total_trades) * 100 if total_trades else 0
    avg_profit = float(positions['ProfitPct'].mean())
    avg_holding = float(positions['HoldingDays'].mean())
    avg_win = float(positions[positions['ProfitPct'] > 0]['ProfitPct'].mean()) if win_trades else 0
    avg_loss = float(positions[positions['ProfitPct'] <= 0]['ProfitPct'].mean()) if loss_trades else 0

    return {
        'total_trades': total_trades,
        'winning_trades': win_trades,
        'losing_trades': loss_trades,
        'win_rate': round(win_rate, 2),
        'average_profit': round(avg_profit, 2),
        'average_holding_days': round(avg_holding, 2),
        'average_win': round(avg_win, 2),
        'average_loss': round(avg_loss, 2),
    }


def render_price_chart(data, positions):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Close Price', line=dict(color='#2563eb', width=2)))
    fig.add_trace(go.Scatter(x=data.index, y=data['MA50'], mode='lines', name='MA50', line=dict(color='#f59e0b', width=2)))
    fig.add_trace(go.Scatter(x=data.index, y=data['MA200'], mode='lines', name='MA200', line=dict(color='#10b981', width=2)))

    if not positions.empty:
        buy_x = [pd.Timestamp(str(date)) for date in positions['BuyDate']]
        buy_y = positions['BuyPrice'].tolist()
        sell_x = [pd.Timestamp(str(date)) for date in positions['SellDate']]
        sell_y = positions['SellPrice'].tolist()

        fig.add_trace(go.Scatter(x=buy_x, y=buy_y, mode='markers', name='Buy', marker=dict(color='red', size=10, symbol='circle')))
        fig.add_trace(go.Scatter(x=sell_x, y=sell_y, mode='markers', name='Sell', marker=dict(color='green', size=10, symbol='circle')))

    fig.update_layout(
        title='MSFT Price with Moving Averages',
        xaxis_title='Date',
        yaxis_title='Price (USD)',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=650,
    )
    st.plotly_chart(fig, use_container_width=True)


st.set_page_config(page_title='Trading Dashboard', layout='wide')

page = st.sidebar.radio('Navigation', ['Price Chart', 'Trade Statistics', 'Detailed Trades'])


data, positions = build_strategy_data()

if page == 'Price Chart':
    st.title('MSFT Price Chart')
    render_price_chart(data, positions)

elif page == 'Trade Statistics':
    st.title('Overall Trade Statistics')
    stats = compute_stats(positions)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Total Trades', stats['total_trades'])
    col2.metric('Winning Trades', stats['winning_trades'])
    col3.metric('Losing Trades', stats['losing_trades'])
    col4.metric('Win Rate', f"{stats['win_rate']}%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric('Average Profit', f"{stats['average_profit']}%")
    col6.metric('Average Win', f"{stats['average_win']}%")
    col7.metric('Average Loss', f"{stats['average_loss']}%")
    col8.metric('Avg Holding Days', stats['average_holding_days'])

else:
    st.title('Detailed Trade Record')
    if positions.empty:
        st.info('No trades were generated.')
    else:
        trade_table = positions.copy()
        trade_table['BuyDate'] = trade_table['BuyDate'].dt.strftime('%Y-%m-%d')
        trade_table['SellDate'] = trade_table['SellDate'].dt.strftime('%Y-%m-%d')
        trade_table['BuyPrice'] = trade_table['BuyPrice'].map(lambda x: f'{x:.2f}')
        trade_table['SellPrice'] = trade_table['SellPrice'].map(lambda x: f'{x:.2f}')
        trade_table['ProfitPct'] = trade_table['ProfitPct'].map(lambda x: f'{x:.2f}%')
        st.dataframe(trade_table, use_container_width=True)
