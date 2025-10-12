import streamlit as st
import main
st.set_page_config(layout="wide")
col1, col2, col3,col4 = st.columns([0.5,0.5,0.5,0.5])

tickers={'000001.ss':"上证", '399001.sz':"深成指",'3033.hk':"恒生科技","880008.ss":"平均股价","588200.ss":"科创芯片ETF","880490.ss":"通信设备","512760.ss":"半导体ETF","512760.sz":"半导体ETF","880493.ss":"中证软件","880329.ss":"小金属","880821.ss":"大盘股","880822.ss":"中盘股","880823.ss":"小盘股"}
with col1:
    new_ticker = st.text_input("Ticker Search")

with col2:
    ticker = st.selectbox(
        'Ticker',
        tickers.keys()
    )
with col3:
    interval = st.selectbox(
       'Interval',
        ('5m', '15m', '60m', '1d', '1wk', '1mo')
    )
with col4:
    source = st.selectbox(
       'Data Source',
        ('tdx','yahoo')
    )
if new_ticker is not None and new_ticker != "":
    ticker=new_ticker
    name=new_ticker
else:
    name=tickers[ticker]
# Display the selection
main.main(ticker, interval, source,name, st=st)