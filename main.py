from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Plot.AnimatePlotDriver import CAnimateDriver
from Plot.PlotDriver import CPlotDriver
import matplotlib.pyplot as plt
import argparse

def get_interval(intervals: str) -> str:

    interval_map = {
        "1m": KL_TYPE.K_1M,
        "5m": KL_TYPE.K_5M,
        "15m": KL_TYPE.K_15M,
        "30m": KL_TYPE.K_30M,
        "60m": KL_TYPE.K_60M,
        "1d": KL_TYPE.K_DAY,
        "1wk": KL_TYPE.K_WEEK,
        "1mo": KL_TYPE.K_MON,
        "3mo": KL_TYPE.K_QUARTER,
    }
    ret=[]
    for interval in intervals.split(","):
        if interval not in interval_map:
            raise ValueError(f"Invalid interval: {interval}")
        ret.append(interval_map[interval])
    return ret
def get_code(ticker: str, data_src:str) -> str:
    ticker=ticker.lower()
    if data_src == DATA_SRC.BAO_STOCK and ticker.startswith(".sz"):
        code = ticker[-2:] + '.' + ticker[:3]
        print(f"convert ticker to {code}")
    elif data_src == DATA_SRC.BAO_STOCK and ticker.endswith(".ss"):
        code = 'sh' + '.' + ticker[:-3]
        print(f"convert ticker to {code}")
    else:
        code = ticker
    return code
if __name__ == "__main__":
    argparser=argparse.ArgumentParser()
    argparser.add_argument("--ticker",type=str,default="sh.000001")
    argparser.add_argument("--interval",type=str,default="1wk,1d", help='1m,5m,15m,30m,60m,1d,1wk,1mo,3mo')
    args=argparser.parse_args()
    data_src = DATA_SRC.BAO_STOCK
    code=get_code(args.ticker,data_src)
    
    begin_time = "2018-01-01"
    end_time = None
    
    #lv_list = [KL_TYPE.K_WEEK, KL_TYPE.K_DAY]
    lv_list = get_interval(args.interval)
    config = CChanConfig({
        "bi_strict": True,
        "trigger_step": False,
        "skip_step": 0,
        "divergence_rate": float("inf"),
        "bsp2_follow_1": False,
        "bsp3_follow_1": False,
        "min_zs_cnt": 0,
        "bs1_peak": False,
        "macd_algo": "peak",
        "bs_type": '1,2,3a,1p,2s,3b',
        "print_warning": True,
        "zs_algo": "normal",
    })

    plot_config = {
        "plot_kline": False,
        "plot_kline_combine": True,
        "plot_bi": True,
        "plot_seg": True,
        "plot_eigen": False,
        "plot_zs": True,
        "plot_macd": False,
        "plot_mean": False,
        "plot_channel": False,
        "plot_bsp": True,
        "plot_extrainfo": False,
        "plot_demark": False,
        "plot_marker": False,
        "plot_rsi": False,
        "plot_kdj": False,
    }

    plot_para = {
        "seg": {
            # "plot_trendline": True,
        },
        "bi": {
            # "show_num": True,
            # "disp_end": True,
        },
        "figure": {
            "x_range": 200,
        },
        "marker": {
            # "markers": {  # text, position, color
            #     '2023/06/01': ('marker here', 'up', 'red'),
            #     '2023/06/08': ('marker here', 'down')
            # },
        }
    }
    chan = CChan(
        code=code,
        begin_time=begin_time,
        end_time=end_time,
        data_src=data_src,
        lv_list=lv_list,
        config=config,
        autype=AUTYPE.QFQ,
    )

    if not config.trigger_step:
        plot_driver = CPlotDriver(
            chan,
            plot_config=plot_config,
            plot_para=plot_para,
        )
        plot_driver.figure.show()
        plot_driver.save2img("./test.png")
    else:
        CAnimateDriver(
            chan,
            plot_config=plot_config,
            plot_para=plot_para,
        )
    manager = plt.get_current_fig_manager()
    manager.window.state('zoomed')
    plt.show()