import struct
import datetime
import numpy as np
import os
import pandas as pd
import sys
from datetime import datetime
from os.path import exists


rootpaths = ['d:/Apps/goldsun/vipdoc/']
def get_tdx_file_path(ticker, interval='1d'):
  exchange=ticker[-2:].lower()
  if exchange == 'ss':
    exchange = 'sh'
  
  for rp in rootpaths:
    if interval=='1d':
      path = f"{rp}{exchange}/lday/{exchange}{ticker[:6]}.day"
    elif interval in ['5m']:
      path = f"{rp}{exchange}/fzline/{exchange}{ticker[:6]}.lc5"
    elif interval in ['1min','1m']:
      path = f"{rp}{exchange}/minline/{exchange}{ticker[:6]}.lc1"  
    if exists(path):
      return path
  return None
def GetTDXData_v4(tickers, bars, interval='1d'):
  df = None
  if isinstance(tickers, list):
    for ticker in tickers:
      ticker=ticker.upper()
      data = GetTDXData_v3(ticker, bars, interval)
      if data is None:
        continue
      data.columns = [(col, ticker) for col in data.columns]
      
      if df is None:
        df = data
      else:
        df = pd.concat([df, data], axis=1)
  else:
    df= GetTDXData_v3(tickers, bars, interval='1d')
  return df

def GetTDXData_v3(symbol, bars, interval='1d'):
  if symbol.count('.')==0:
    return None
  #for path in paths:
  filename = get_tdx_file_path(symbol, interval)
  if filename != None:
    if interval=='1d':
      record_dtype = np.dtype([
      ('Date', 'u4'),
      ('Open', 'u4'),      # 2-byte integer (big-endian)
      ('High', 'u4'),      # 2-byte integer (big-endian)
      ('Low', 'u4'),      # 2-byte integer (big-endian)
      ('Close', 'u4'),      # 2-byte integer (big-endian)
      ('Amount', 'f4'),      # 2-byte integer (big-endian)
      ('Volume', 'u4'),      # 2-byte integer (big-endian)
      ('stock_reservation', 'u4')      # 2-byte integer (big-endian)
      ])     

      records =np.fromfile(filename, dtype=record_dtype)
      df=pd.DataFrame(records)
      date_strings = np.char.mod('%08d', df['Date'].values) 
      df.index =  pd.to_datetime(date_strings, format='%Y%m%d')
      df.drop(columns=['stock_reservation','Date'], inplace=True)
      df['Open']= np.divide(records['Open'], 100)
      df['High']= np.divide(records['High'], 100)
      df['Low']= np.divide(records['Low'], 100)
      df['Close']= np.divide(records['Close'], 100)
      df['Vwap'] = df['Amount']/df['Volume']
      return df
    elif interval in ['5m']:
      record_dtype = np.dtype([      
      ('Date', 'u2'),
      ('Min', 'u2'),
      ('Open', 'f4'),      # 2-byte integer (big-endian)
      ('High', 'f4'),      # 2-byte integer (big-endian)
      ('Low', 'f4'),      # 2-byte integer (big-endian)
      ('Close', 'f4'),      # 2-byte integer (big-endian)
      ('Amount', 'f4'),      # 2-byte integer (big-endian)
      ('Volume', 'u4'),      # 2-byte integer (big-endian)
      ('stock_reservation', 'u4')      # 2-byte integer (big-endian)
      ]) 
      records =np.fromfile(filename, dtype=record_dtype)
      df=pd.DataFrame(records) 
      date_int =np.char.mod('%04d', df['Date'].values).astype(int)
      min_int =np.char.mod('%04d', df['Min'].values).astype(int)
      df.index= df.index =  pd.to_datetime(
      {
        'year': date_int//2048+2004,
        'month': np.mod(date_int,2048)//100,
        'day': np.mod(np.mod(date_int,2048),100),
        'hour': min_int//60,
        'minute': np.mod(min_int,60)
      })
      df.drop(columns=['stock_reservation','Date','Min'], inplace=True)
      df['Vwap'] = df['Amount']/df['Volume']
      return df[-bars:]
  return None



if __name__ == '__main__':
  print(sys.version)
  start=datetime.now()
  #df=GetTDXData_v3('002049.sz',500,'1d')
  df=GetTDXData_v4(['002049.sz'],500,'5m')
  print(len(df))
  print(df.tail(10))
  end=datetime.now()
  print(end-start)