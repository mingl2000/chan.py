from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Plot.AnimatePlotDriver import CAnimateDriver
from Plot.PlotDriver import CPlotDriver
from ElliottWave import validate_fractal, format_fractal_report
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
def is_index(ticker: str) -> bool:
    ticker=ticker.lower()
    if ticker in ["000001.ss","000300.ss","000905.ss","000016.ss","sh.000001","sh.000300","sh.000905","sh.000016","399001.sz","399006.sz","sz.399001","sz.399006","000688.ss"]:
        return True
    return False
def get_code(ticker: str, inerval, source) -> str:
    ticker=ticker.lower()
    if source == "tdx":
        data_src = DATA_SRC.TDX_API
    elif source == "yahoo":
        data_src = DATA_SRC.YAHOO_API
    else:
        data_src = DATA_SRC.BAO_STOCK
        if ticker.endswith(".ss"):    
            ticker = 'sh' + '.' + ticker[:-3]
        elif ticker.endswith(".sz"):
            data_src = DATA_SRC.BAO_STOCK
        ticker = 'sz' + '.' + ticker[:-3]

    return ticker,data_src

def main(ticker, interval, source, name,st=None,bars=500,x_range=400,elliott=True):
    code, data_src=get_code(ticker, interval,source)

    # TDX数据源拉取的K线根数(硬编码500根的替代)，仅对tdx源生效
    if source == "tdx":
        from DataAPI.TDXAPI import TDX_API
        TDX_API.bars = bars

    begin_time = "2000-01-01"
    end_time = None
    
    lv_list = get_interval(interval)
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
        "print_warning": False,
        "zs_algo": "normal",
        # 多级别时高/低级别历史长度常不一致(如TDX日线很长、分钟线仅数百根)，
        # 关闭对齐检查避免因老K线在次级别找不到子K线而报错；分形校验只在有重叠的区间生效。
        "kl_data_check": False,
    })

    plot_config = {
        "plot_kline": False,
        "plot_kline_combine": True,
        "plot_bi": True,
        "plot_seg": True,
        "plot_eigen": False,
        "plot_zs": True,
        "plot_elliott": elliott,
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
        "elliott": {
            # 要标注的浪级(degree): 'bi'=笔/次级Minor, 'seg'=线段/中级Intermediate, 'segseg'=段中段/主级Primary
            "degrees": ("bi", "seg"),
            "show_fib": False,       # True=在最近一段腿上叠加斐波那契回撤位以预测目标
            "allow_diagonal": True,  # True=严格数不出浪时回退斜纹模式(日线保持严格,分钟级也能出浪); False=始终严格
        },
        "figure": {
            "x_range": x_range,
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
        name=name,
    )

    # 传入多级别(如 --interval 1d,15m)时，做跨周期艾略特分形校验并打印报告
    if len(lv_list) >= 2:
        rows = validate_fractal(chan, high_idx=0, low_idx=1)
        print(format_fractal_report(rows, high_name=lv_list[0].name.split('K_')[1], low_name=lv_list[1].name.split('K_')[1]))

    if not config.trigger_step:
        plot_driver = CPlotDriver(
            chan,
            plot_config=plot_config,
            plot_para=plot_para,
        )
        if st is None:
            plot_driver.figure.show()
        else:    
            fig=plt.gcf()
            st.pyplot(fig)
        plot_driver.save2img(f"./{ticker}_{interval}.png")
    else:
        CAnimateDriver(
            chan,
            plot_config=plot_config,
            plot_para=plot_para,
        )
    if st is None:
        manager = plt.get_current_fig_manager()
        manager.window.state('zoomed')
        manager.set_window_title(args.ticker)
        plt.show()
    else:
        pass
        #fig=plt.gcf()
        #st.pyplot(fig)
if __name__ == "__main__":
    argparser=argparse.ArgumentParser()
    argparser.add_argument("--ticker",type=str,default="000001.ss")
    argparser.add_argument("--interval",type=str,default="15m", help='1m,5m,15m,30m,60m,1d,1wk,1mo,3mo')
    argparser.add_argument("--source",type=str,default="tdx", help='tdx,yahoo,baostock')
    argparser.add_argument("--name",type=str,default="车上", help='', required=False)
    argparser.add_argument("--bars",type=int,default=500, help='TDX数据源拉取的K线根数(分钟级为5m根数),默认500', required=False)
    argparser.add_argument("--xrange",type=int,default=400, help='图上显示的K线根数(窗口宽度),默认400。加大以显示更长历史/更高浪级', required=False)
    argparser.add_argument("--elliott",action=argparse.BooleanOptionalAction,default=True, help='是否叠加艾略特波浪标注(--elliott/--no-elliott),默认开启')
    args=argparser.parse_args()
    if args.name=="":
        args.name=args.ticker
    main(args.ticker, args.interval,args.source, args.name, bars=args.bars, x_range=args.xrange, elliott=args.elliott)