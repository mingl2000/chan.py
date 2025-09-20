import os

from Common.CEnum import DATA_FIELD, KL_TYPE
from Common.ChanException import CChanException, ErrCode
from Common.CTime import CTime
from Common.func_util import str2float
from KLine.KLine_Unit import CKLine_Unit

from .CommonStockAPI import CCommonStockApi
import yfinance as yf

def create_item_dict(data, column_name):
    for i in range(len(data)):
        data[i] = parse_time_column(data[i]) if column_name[i] == DATA_FIELD.FIELD_TIME else str2float(data[i])
    return dict(zip(column_name, data))


def parse_time_column(inp):
    # 20210902113000000
    # 2021-09-13
    if len(inp) == 10:
        year = int(inp[:4])
        month = int(inp[5:7])
        day = int(inp[8:10])
        hour = minute = 0
    elif len(inp) == 17:
        year = int(inp[:4])
        month = int(inp[4:6])
        day = int(inp[6:8])
        hour = int(inp[8:10])
        minute = int(inp[10:12])
    elif len(inp) == 19:
        year = int(inp[:4])
        month = int(inp[5:7])
        day = int(inp[8:10])
        hour = int(inp[11:13])
        minute = int(inp[14:16])
    else:
        raise Exception(f"unknown time column from csv:{inp}")
    return CTime(year, month, day, hour, minute)


class YAHOO_API(CCommonStockApi):
    def __init__(self, code, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=None):
        self.headers_exist = True  # 第一行是否是标题，如果是数据，设置为False
        self.columns = [
            DATA_FIELD.FIELD_TIME,
            DATA_FIELD.FIELD_OPEN,
            DATA_FIELD.FIELD_HIGH,
            DATA_FIELD.FIELD_LOW,
            DATA_FIELD.FIELD_CLOSE,
            # DATA_FIELD.FIELD_VOLUME,
            # DATA_FIELD.FIELD_TURNOVER,
            # DATA_FIELD.FIELD_TURNRATE,
        ]  # 每一列字段
        self.time_column_idx = self.columns.index(DATA_FIELD.FIELD_TIME)
        super(YAHOO_API, self).__init__(code, k_type, begin_date, end_date, autype)

    def get_kl_data(self):
        #df=yf.download(self.code, start=self.begin_date, end=self.end_date, interval=self.k_type.name[2:].lower(), progress=False)
        print(f"download {self.code} from {self.begin_date} to {self.end_date} by {self.k_type.name[2:].lower()}")
        df=yf.download(self.code, start=self.begin_date, end=self.end_date, interval='1d', progress=False)
        df=df.droplevel(1,axis=1)
        df=df[['Open','High','Low','Close']]
        df=df.reset_index()
        for idx, row in df.iterrows():
            data = [
                row.values[0].strftime('%Y-%m-%d'),
                round(row.values[1],4),
                round(row.values[2],4),
                round(row.values[3],4),
                round(row.values[4],4),
            ]
            yield CKLine_Unit(create_item_dict(data, self.columns))

    def SetBasciInfo(self):
        pass

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass
