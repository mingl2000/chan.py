import streamlit as st
import main
col1, col2, col3 = st.columns(3)
with col1:
    ticker = st.selectbox(
        'Ticker',
        ('000001.ss', '399001.sz', '3033.hk')
    )
with col2:
    interval = st.selectbox(
       'Interval',
        ('5m', '15m', '60m', '1d', '1wk', '1mo')
    )
with col3:
    source = st.selectbox(
       'Data Source',
        ('tdx','yahoo')
    )
# Display the selection
name="上证"
st.write('You selected:', ticker, interval, source)
main.main(ticker, interval, source,name, st=st)