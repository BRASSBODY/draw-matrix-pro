import streamlit as st
import pandas as pd
import sqlite3
import requests
from datetime import datetime
import plotly.express as px
import os

# Page config
st.set_page_config(
    page_title="Draw Matrix Pro",
    page_icon="⚽",
    layout="wide"
)

# Title
st.title("⚽ Draw Matrix Pro")
st.caption("Live Draw Predictions & Betting Dashboard")

# Database path
DB_PATH = "data/draw_matrix_pro.db"

# Sidebar
st.sidebar.header("Controls")

# Connect to database
@st.cache_resource
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

# Load recommendations
@st.cache_data(ttl=60)
def load_recommendations():
    try:
        conn = get_db()
        df = pd.read_sql_query("""
            SELECT 
                id, home_team, away_team, tournament,
                draw_odds, heatmap_score as draw_prob,
                recommendation, confidence, result,
                created_at, roi
            FROM recommendations
            ORDER BY created_at DESC
            LIMIT 50
        """, conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

# Load performance stats
@st.cache_data(ttl=60)
def load_performance():
    try:
        conn = get_db()
        df = pd.read_sql_query("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(roi) as total_roi,
                AVG(heatmap_score) as avg_prob
            FROM recommendations
            WHERE result != 'PENDING'
        """, conn)
        conn.close()
        return df.iloc[0] if not df.empty else None
    except:
        return None

# Fetch live matches from API
def fetch_live_matches():
    token = "acec18e5caf0091791d1afee0a220d04140fc040"
    headers = {"Authorization": f"Token {token}"}
    
    try:
        r = requests.get(
            "https://sports.bzzoiro.com/api/v2/events/live/",
            headers=headers,
            timeout=10
        )
        data = r.json()
        return data.get('events', [])
    except:
        return []

# Main layout
col1, col2, col3, col4 = st.columns(4)

# Performance metrics
perf = load_performance()
if perf is not None and perf['total'] is not None:
    col1.metric("Total Bets", int(perf['total']))
    col2.metric("Wins", int(perf['wins']) if perf['wins'] is not None else 0)
    col3.metric("Win Rate", f"{perf['wins']/perf['total']*100:.1f}%" if perf['total'] > 0 else "0%")
    col4.metric("Total ROI", f"{perf['total_roi']:.2f} units" if perf['total_roi'] is not None else "0.00 units")
else:
    col1.metric("Total Bets", 0)
    col2.metric("Wins", 0)
    col3.metric("Win Rate", "0%")
    col4.metric("Total ROI", "0.00 units")

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Recommendations", "🔄 Live Matches", "📈 Performance"])

with tab1:
    st.subheader("Recent Recommendations")
    df = load_recommendations()
    
    if not df.empty:
        # Color coding
        def color_rec(val):
            if val == 'BET':
                return 'background-color: #4CAF50; color: white'
            elif val == 'BORDERLINE':
                return 'background-color: #FFC107; color: black'
            return ''
        
        def color_result(val):
            if val == 'WIN':
                return 'background-color: #4CAF50; color: white'
            elif val == 'LOSS':
                return 'background-color: #f44336; color: white'
            return ''
        
        st.dataframe(
            df.style.applymap(color_rec, subset=['recommendation'])
              .applymap(color_result, subset=['result'])
              .format({
                  'draw_odds': '{:.2f}',
                  'draw_prob': '{:.1%}',
                  'roi': '{:.2f}'
              }),
            use_container_width=True,
            height=400
        )
    else:
        st.info("No recommendations yet. Run the analysis!")

with tab2:
    st.subheader("Live Matches")
    
    if st.button("🔄 Refresh Live Matches"):
        st.cache_data.clear()
    
    events = fetch_live_matches()
    
    if events:
        live_data = []
        for e in events:
            live_data.append({
                "Home": e.get('home_team', ''),
                "Away": e.get('away_team', ''),
                "League": e.get('league_name', ''),
                "Score": f"{e.get('home_score', 0)}-{e.get('away_score', 0)}",
                "Minute": e.get('current_minute', 0),
                "Status": e.get('status', '')
            })
        df_live = pd.DataFrame(live_data)
        st.dataframe(df_live, use_container_width=True)
    else:
        st.info("No live matches at the moment. Check back later!")

with tab3:
    st.subheader("Performance Dashboard")
    
    # Historical performance
    try:
        conn = get_db()
        history = pd.read_sql_query("""
            SELECT 
                strftime('%Y-%m-%d', created_at) as date,
                COUNT(*) as bets,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(roi) as roi
            FROM recommendations
            WHERE result != 'PENDING'
            GROUP BY date
            ORDER BY date DESC
            LIMIT 30
        """, conn)
        conn.close()
        
        if not history.empty:
            fig = px.bar(
                history,
                x='date',
                y=['wins', 'bets'],
                title="Daily Performance",
                barmode='group'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # ROI trend
            fig2 = px.line(
                history,
                x='date',
                y='roi',
                title="Daily ROI (units)"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No performance data yet. Start betting!")
    except:
        st.info("No performance data yet. Start betting!")

# Refresh button
if st.sidebar.button("🔄 Run Analysis Now"):
    import subprocess
    with st.spinner("Running analysis..."):
        result = subprocess.run(["python", "draw_agent.py"], capture_output=True, text=True)
        if result.returncode == 0:
            st.success("✅ Analysis complete! Check the Recommendations tab.")
        else:
            st.error(f"❌ Analysis failed: {result.stderr}")
        st.cache_data.clear()
        st.rerun()

# Run scheduler
if st.sidebar.button("🔄 Start Scheduler"):
    import subprocess
    with st.spinner("Starting scheduler..."):
        subprocess.Popen(["python", "scheduler.py"], shell=True)
        st.success("✅ Scheduler started! Running every 30 minutes.")
        st.cache_data.clear()

st.sidebar.caption("Data updates every 60 seconds")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")