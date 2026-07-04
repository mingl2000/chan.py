"""
纯Python移植的艾略特波浪引擎，思路来自流行的开源项目 ElliottWaveAnalyzer：
  - MonoWave(单波) + skip：直接在K线的高低点上构造方向性摆动，skip可把若干次级回撤
    合并进同一个更大的摆动，从而在同一批K线上表达不同"粒度/级别"的浪。
  - 组合式搜索：对5浪用 [i,j,k,l,m] 全部skip组合逐一尝试，对每个候选按规则校验。
  - 规则集：Impulse(推动,~13条)、LeadingDiagonal(引导斜纹)、Correction(ABC调整)。
与原缠论笔/线段贪心数浪不同，本引擎会在窗口内探索大量组合并保留通过规则的计数。

移植说明：去掉了原项目的 numba @njit(纯Python实现，几百到几千根K线足够快)；
下行(bear)推动通过把序列取负(invert)复用同一套"上行"规则来识别。
"""
from typing import List, Optional


# --------------------------------------------------------------------------- #
# 枢轴查找(纯Python移植 functions.py)
# --------------------------------------------------------------------------- #
def _hi(lows, highs, idx_start=0):
    high = lows[idx_start]
    high_idx = idx_start
    for idx in range(idx_start + 1, len(highs)):
        act = highs[idx]
        if act > high:
            high, high_idx = act, idx
        else:
            return high, high_idx
    return high, high_idx


def _next_hi(lows, highs, idx_start, prev_high):
    high = lows[idx_start]
    high_idx = None
    prev_reached = False
    for idx in range(idx_start + 1, len(highs)):
        act = highs[idx]
        if act < prev_high and not prev_reached:
            continue
        elif act > prev_high and not prev_reached:
            prev_reached = True
            high, high_idx = act, idx
        elif act > high:
            high, high_idx = act, idx
        else:
            return high, high_idx
    return None, None


def _lo(lows, highs, idx_start):
    low = highs[idx_start]
    low_idx = idx_start
    for idx in range(idx_start + 1, len(lows)):
        act = lows[idx]
        if act < low:
            low, low_idx = act, idx
        else:
            return low, low_idx
    return low, low_idx


def _next_lo(lows, highs, idx_start, prev_low):
    low = highs[idx_start]
    low_idx = None
    prev_reached = False
    for idx in range(idx_start + 1, len(lows)):
        act = lows[idx]
        if act > prev_low and not prev_reached:
            continue
        elif act < prev_low and not prev_reached:
            prev_reached = True
            low, low_idx = act, idx
        elif act < low:
            low, low_idx = act, idx
        else:
            return low, low_idx
    return None, None


# --------------------------------------------------------------------------- #
# MonoWave(单波) + skip
# --------------------------------------------------------------------------- #
class MonoWave:
    def __init__(self, lows, highs, dates, idx_start, skip=0):
        self.lows_arr = lows
        self.highs_arr = highs
        self.dates_arr = dates
        self.skip_n = skip
        self.idx_start = idx_start
        self.idx_end = None
        self.up = None
        self.low = self.high = 0.0
        self.low_idx = self.high_idx = idx_start
        self.date_start = self.date_end = None

    @property
    def length(self):
        return abs(self.high - self.low)

    @property
    def duration(self):
        return (self.idx_end - self.idx_start) if self.idx_end is not None else 0


class MonoWaveUp(MonoWave):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.up = True
        self.high, self.high_idx = self._find_end()
        self.low = self.lows_arr[self.idx_start]
        self.low_idx = self.idx_start
        if self.high_idx is not None:
            self.idx_end = self.high_idx
            self.date_start = self.dates_arr[self.idx_start]
            self.date_end = self.dates_arr[self.high_idx]

    def _find_end(self):
        high, high_idx = _hi(self.lows_arr, self.highs_arr, self.idx_start)
        low_at_start = self.lows_arr[self.idx_start]
        if high is None:
            return None, None
        for _ in range(self.skip_n):
            act, act_idx = _next_hi(self.lows_arr, self.highs_arr, high_idx, high)
            if act is None:
                return None, None
            if act > high:
                # 合并该次级回撤前，回撤不能跌破本摆动起点
                if min(self.lows_arr[self.idx_start:act_idx]) < low_at_start:
                    return None, None
                high, high_idx = act, act_idx
        return high, high_idx


class MonoWaveDown(MonoWave):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.up = False
        self.low, self.low_idx = self._find_end()
        self.high = self.highs_arr[self.idx_start]
        self.high_idx = self.idx_start
        if self.low is not None:
            self.idx_end = self.low_idx
            self.date_start = self.dates_arr[self.idx_start]
            self.date_end = self.dates_arr[self.low_idx]

    def _find_end(self):
        low, low_idx = _lo(self.lows_arr, self.highs_arr, self.idx_start)
        high_at_start = self.highs_arr[self.idx_start]
        if low is None:
            return None, None
        for _ in range(self.skip_n):
            act, act_idx = _next_lo(self.lows_arr, self.highs_arr, low_idx, low)
            if act is None:
                return None, None
            if act < low:
                if max(self.highs_arr[self.idx_start:act_idx]) > high_at_start:
                    return None, None
                low, low_idx = act, act_idx
        return low, low_idx


# --------------------------------------------------------------------------- #
# WaveOptions 组合生成(移植 WaveOptions.py 的剪枝逻辑)
# --------------------------------------------------------------------------- #
def gen_options5(up_to, prune=True):
    """
    返回 [i,j,k,l,m] skip组合。
    prune=True(默认,快)：原项目剪枝——出现0之后其余必须为0(适合平铺小浪,组合少)。
    prune=False(全量)：所有组合，允许如[0,2,3,0,0](某浪不合并、后一浪需大幅合并)，
                        主级大浪常需要它，但组合更多(仅用于枢轴少的主级搜索)。
    """
    if not prune:
        import itertools
        return list(itertools.product(range(up_to), repeat=5))
    opts = set()
    for i in range(up_to):
        for j in range(up_to):
            for k in range(up_to):
                for l in range(up_to):
                    for m in range(up_to):
                        ii, jj, kk, ll, mm = i, j, k, l, m
                        if ii == 0:
                            jj = kk = ll = mm = 0
                        if jj == 0:
                            kk = ll = mm = 0
                        if kk == 0:
                            ll = mm = 0
                        if ll == 0:
                            mm = 0
                        opts.add((ii, jj, kk, ll, mm))
    return sorted(opts)


def gen_options3(up_to, prune=True):
    if not prune:
        import itertools
        return list(itertools.product(range(up_to), repeat=3))
    opts = set()
    for i in range(up_to):
        for j in range(up_to):
            for k in range(up_to):
                ii, jj, kk = i, j, k
                if ii == 0:
                    jj = kk = 0
                if jj == 0:
                    kk = 0
                opts.add((ii, jj, kk))
    return sorted(opts)


# --------------------------------------------------------------------------- #
# 规则集(移植 WaveRules.py 的 lambda 条件字典)
# --------------------------------------------------------------------------- #
class WaveRule:
    def __init__(self, name):
        self.name = name
        self.conditions = self.set_conditions()

    def set_conditions(self):
        raise NotImplementedError


class Impulse(WaveRule):
    def set_conditions(self):
        return {
            "w2_1": {"waves": ["wave1", "wave2"], "function": lambda w1, w2: w2.low > w1.low,
                     "message": "End of Wave2 lower than Start of Wave1"},
            "w2_2": {"waves": ["wave1", "wave2"], "function": lambda w1, w2: w2.length >= 0.2 * w1.length,
                     "message": "Wave2 shorter than 20% of Wave1"},
            "w2_3": {"waves": ["wave1", "wave2"], "function": lambda w1, w2: 9 * w2.duration > w1.duration,
                     "message": "Wave2 longer than 9x Wave1 (time)"},
            "w3_1": {"waves": ["wave1", "wave3", "wave5"],
                     "function": lambda w1, w3, w5: not (w3.length < w5.length and w3.length < w1.length),
                     "message": "Wave3 is the shortest wave"},
            "w3_2": {"waves": ["wave1", "wave3"], "function": lambda w1, w3: w3.high > w1.high,
                     "message": "End of Wave3 lower than End of Wave1"},
            "w3_3": {"waves": ["wave1", "wave3"], "function": lambda w1, w3: w3.length >= w1.length / 3.0,
                     "message": "Wave3 shorter than 1/3 of Wave1"},
            "w3_4": {"waves": ["wave2", "wave3"], "function": lambda w2, w3: w3.length > w2.length,
                     "message": "Wave3 shorter than Wave2"},
            "w3_5": {"waves": ["wave1", "wave3"], "function": lambda w1, w3: 7 * w3.duration > w1.duration,
                     "message": "Wave3 >7x Wave1 (time)"},
            "w4_1": {"waves": ["wave1", "wave4"], "function": lambda w1, w4: w4.low > w1.high,
                     "message": "Wave4 overlaps Wave1 territory"},
            "w4_2": {"waves": ["wave2", "wave4"], "function": lambda w2, w4: w4.length > w2.length / 3.0,
                     "message": "Wave4 shorter than 1/3 of Wave2"},
            "w5_1": {"waves": ["wave3", "wave5"], "function": lambda w3, w5: w3.high < w5.high,
                     "message": "End of Wave5 lower than End of Wave3"},
            "w5_2": {"waves": ["wave1", "wave5"], "function": lambda w1, w5: w5.length < 2.0 * w1.length,
                     "message": "Wave5 longer than 2x Wave1"},
        }


class LeadingDiagonal(WaveRule):
    @staticmethod
    def _slope(x1, x2, y1, y2):
        return (y2 - y1) / (x2 - x1) if x2 != x1 else 0.0

    def set_conditions(self):
        s = self._slope
        return {
            "w2_0": {"waves": ["wave1", "wave2", "wave3", "wave4"],
                     "function": lambda w1, w2, w3, w4: s(w2.idx_end, w4.idx_end, w2.low, w4.low)
                     > s(w1.idx_end, w3.idx_end, w1.high, w3.high) > 0,
                     "message": "Wave1-3/Wave2-4 trendlines not converging (diagonal)"},
            "w2_1": {"waves": ["wave1", "wave2"], "function": lambda w1, w2: w2.low > w1.low,
                     "message": "End of Wave2 lower than Start of Wave1"},
            "w2_2": {"waves": ["wave1", "wave2"], "function": lambda w1, w2: w2.length >= 0.2 * w1.length,
                     "message": "Wave2 shorter than 20% of Wave1"},
            "w3_1": {"waves": ["wave1", "wave3", "wave5"],
                     "function": lambda w1, w3, w5: not (w3.length < w5.length and w3.length < w1.length),
                     "message": "Wave3 is the shortest wave"},
            "w3_2": {"waves": ["wave1", "wave3"], "function": lambda w1, w3: w3.high > w1.high,
                     "message": "End of Wave3 lower than End of Wave1"},
            "w3_4": {"waves": ["wave2", "wave3"], "function": lambda w2, w3: w3.length > w2.length,
                     "message": "Wave3 shorter than Wave2"},
            "w4_1": {"waves": ["wave1", "wave4"], "function": lambda w1, w4: w4.low < w1.high,
                     "message": "Wave4 not overlapping Wave1 (needed for diagonal)"},
            "w5_1": {"waves": ["wave3", "wave5"], "function": lambda w3, w5: w3.high < w5.high,
                     "message": "End of Wave5 lower than End of Wave3"},
            "w5_4": {"waves": ["wave3", "wave5"], "function": lambda w3, w5: w5.length < w3.length,
                     "message": "Wave5 not shorter than Wave3"},
        }


class Correction(WaveRule):
    def set_conditions(self):
        return {
            "c1": {"waves": ["wave1", "wave2"], "function": lambda a, b: a.high > b.high,
                   "message": "End of WaveB higher than Start of WaveA"},
            "c2": {"waves": ["wave1", "wave3"], "function": lambda a, c: a.low > c.low,
                   "message": "End of WaveC not below Start of WaveA"},
            "c3": {"waves": ["wave1", "wave2"], "function": lambda a, b: a.length > b.length,
                   "message": "WaveB longer than WaveA"},
            "c5": {"waves": ["wave1", "wave3"], "function": lambda a, c: c.length > 0.6 * a.length,
                   "message": "WaveC shorter than 0.6x WaveA"},
            "c6": {"waves": ["wave1", "wave3"], "function": lambda a, c: c.length < 2.61 * a.length,
                   "message": "WaveC longer than 2.61x WaveA"},
            "c7": {"waves": ["wave1", "wave2"], "function": lambda a, b: b.length > 0.35 * a.length,
                   "message": "WaveB shorter than 0.35x WaveA"},
        }


# --------------------------------------------------------------------------- #
# WavePattern + WaveAnalyzer
# --------------------------------------------------------------------------- #
class WavePattern:
    def __init__(self, waves, verbose=False):
        self.waves_list = waves
        self.waves = {f"wave{i + 1}": w for i, w in enumerate(waves)}
        self.verbose = verbose

    @property
    def idx_start(self):
        return self.waves_list[0].idx_start

    @property
    def idx_end(self):
        return self.waves_list[-1].idx_end

    def check_rule(self, rule):
        for _name, cond in rule.conditions.items():
            args = [self.waves[wn] for wn in cond["waves"]]
            if not cond["function"](*args):
                if self.verbose:
                    print(cond["message"])
                return False
        return True

    def signature(self):
        return tuple(w.idx_end for w in self.waves_list)


class WaveAnalyzer:
    def __init__(self, highs, lows, dates):
        self.highs = highs
        self.lows = lows
        self.dates = dates

    def find_impulsive_wave(self, idx_start, cfg):
        w1 = MonoWaveUp(self.lows, self.highs, self.dates, idx_start, skip=cfg[0])
        if w1.idx_end is None:
            return None
        w2 = MonoWaveDown(self.lows, self.highs, self.dates, w1.idx_end, skip=cfg[1])
        if w2.idx_end is None:
            return None
        w3 = MonoWaveUp(self.lows, self.highs, self.dates, w2.idx_end, skip=cfg[2])
        if w3.idx_end is None:
            return None
        w4 = MonoWaveDown(self.lows, self.highs, self.dates, w3.idx_end, skip=cfg[3])
        if w4.idx_end is None:
            return None
        seg = self.lows[w2.low_idx:w4.low_idx]
        if seg and w2.low > min(seg):
            return None
        w5 = MonoWaveUp(self.lows, self.highs, self.dates, w4.idx_end, skip=cfg[4])
        if w5.idx_end is None:
            return None
        seg2 = self.lows[w4.low_idx:w5.high_idx]
        if seg2 and w4.low > min(seg2):
            return None
        return [w1, w2, w3, w4, w5]

    def find_corrective_wave(self, idx_start, cfg):
        a = MonoWaveDown(self.lows, self.highs, self.dates, idx_start, skip=cfg[0])
        if a.idx_end is None:
            return None
        b = MonoWaveUp(self.lows, self.highs, self.dates, a.idx_end, skip=cfg[1])
        if b.idx_end is None:
            return None
        c = MonoWaveDown(self.lows, self.highs, self.dates, b.idx_end, skip=cfg[2])
        if c.idx_end is None:
            return None
        return [a, b, c]


# --------------------------------------------------------------------------- #
# 高层封装：在可见窗口内找最佳推动(+其后ABC)，支持上/下行
# --------------------------------------------------------------------------- #
def _real_point(w, inverted):
    """把单波终点映射为真实坐标: (idx, price, is_peak)。inverted表示在取负空间内求得。"""
    if not inverted:
        return (w.idx_end, w.high, True) if w.up else (w.idx_end, w.low, False)
    # 取负空间: 上行↔真实下行
    return (w.idx_end, -w.high, False) if w.up else (w.idx_end, -w.low, True)


def _points(waves, labels, inverted):
    return [(_real_point(w, inverted) + (lab,)) for w, lab in zip(waves, labels)]  # (idx,price,is_peak,label)


def _find_valid_impulses(wa, idx_start, up_to, rules, full=False):
    results = []
    seen = set()
    for cfg in gen_options5(up_to, prune=not full):
        waves = wa.find_impulsive_wave(idx_start, cfg)
        if not waves:
            continue
        wp = WavePattern(waves)
        for rule in rules:
            if wp.check_rule(rule):
                sig = wp.signature()
                if sig in seen:
                    break
                seen.add(sig)
                results.append((wp, rule.name))
                break
    return results


def _find_valid_corrections(wa, idx_start, up_to, full=False):
    rule = Correction("correction")
    seen = set()
    out = []
    for cfg in gen_options3(up_to, prune=not full):
        waves = wa.find_corrective_wave(idx_start, cfg)
        if not waves:
            continue
        wp = WavePattern(waves)
        if wp.check_rule(rule):
            sig = wp.signature()
            if sig not in seen:
                seen.add(sig)
                out.append(wp)
    return out


_IMP_RULES = [Impulse("impulse"), LeadingDiagonal("leading diagonal")]


def _best_impulse_from(H, L, D, idx_start, up_to, down, full=False):
    """从 idx_start 找该方向(down=True为下行)覆盖最大的合法5浪推动。返回(points,end_idx)或None。"""
    if down:  # 取负空间: 上行引擎 == 真实下行
        wa = WaveAnalyzer([-x for x in L], [-x for x in H], D)
        inverted = True
    else:
        wa = WaveAnalyzer(H, L, D)
        inverted = False
    res = _find_valid_impulses(wa, idx_start, up_to, _IMP_RULES, full=full)
    if not res:
        return None
    wp, _name = max(res, key=lambda r: (r[0].idx_end - r[0].idx_start, r[0].idx_end))
    return _points(wp.waves_list, ["1", "2", "3", "4", "5"], inverted), wp.idx_end


def _best_correction_from(H, L, D, idx_start, up_to, corr_down, full=False):
    """从 idx_start 找ABC调整。corr_down=True调整方向向下(A从高点向下)。返回(points,end_idx)或None。"""
    if corr_down:  # A下-B上-C下: 直接用非取负引擎
        wa = WaveAnalyzer(H, L, D)
        inverted = False
    else:  # 调整向上(A上-B下-C上): 取负空间
        wa = WaveAnalyzer([-x for x in L], [-x for x in H], D)
        inverted = True
    corrs = _find_valid_corrections(wa, idx_start, up_to, full=full)
    if not corrs:
        return None
    cwp = max(corrs, key=lambda w: w.idx_end - w.idx_start)
    return _points(cwp.waves_list, ["A", "B", "C"], inverted), cwp.idx_end


def _pivots(H, L, xb, xe, k=4):
    """k-bar分形枢轴：返回窗口内的局部低点索引、局部高点索引(各自去重相邻)。"""
    los, his = [], []
    for i in range(xb, xe + 1):
        a, b = max(xb, i - k), min(xe + 1, i + k + 1)
        if L[i] <= min(L[a:b]):
            los.append(i)
        if H[i] >= max(H[a:b]):
            his.append(i)

    def thin(idxs):
        out = []
        for i in idxs:
            if not out or i - out[-1] > k:
                out.append(i)
        return out
    return thin(los), thin(his)


def _cap(anchors, cap):
    """锚点过多时按位置均匀抽样到cap个，保证空间覆盖并限制计算量。"""
    if len(anchors) <= cap:
        return anchors
    step = len(anchors) / cap
    return [anchors[int(i * step)] for i in range(cap)]


def _zigzag(H, L, xb, xe, k):
    """把窗口压成交替的高/低枢轴序列(降噪)，返回 [(orig_idx, 'H'/'L', price), ...]。"""
    los, his = _pivots(H, L, xb, xe, k)
    piv = sorted([(i, 'L') for i in los] + [(i, 'H') for i in his])
    seq = []
    for idx, typ in piv:
        price = L[idx] if typ == 'L' else H[idx]
        if seq and seq[-1][1] == typ:  # 相邻同类型，保留更极端者
            if (typ == 'H' and price > seq[-1][2]) or (typ == 'L' and price < seq[-1][2]):
                seq[-1] = (idx, typ, price)
        else:
            seq.append((idx, typ, price))
    return seq


def _analyze_major(H, L, xb, xe, up_to):
    """在窗口主要枢轴的zigzag上找【主级(最大)】5浪推动(+其后ABC)，把索引映射回原始K线x。"""
    k = max(4, (xe - xb) // 40)              # 枢轴粒度随窗口大小自适应
    seq = _zigzag(H, L, xb, xe, k)
    if len(seq) < 6:
        return []
    prices = [p for _, _, p in seq]
    Ds = list(range(len(seq)))               # 以zigzag位置为“K线”(高=低=枢轴价)
    lo_r = min(range(len(seq)), key=lambda i: prices[i])
    hi_r = max(range(len(seq)), key=lambda i: prices[i])

    up_to_major = max(up_to, 6)              # 主级需较大skip合并大量次级回撤
    best = None                              # (span, pts, end, inverted, anchor)
    for anchor, down in [(lo_r, False), (hi_r, True)]:
        # full=True: 用全量组合(允许如[0,2,3,0,0])，枢轴少所以仍然很快
        f = _best_impulse_from(prices, prices, Ds, anchor, up_to_major, down, full=True)
        if f:
            pts, end = f
            span = end - anchor
            if best is None or span > best[0]:
                best = (span, pts, end, down, anchor)
    if best is None:
        return []
    _span, pts, end, inverted, anchor = best

    def remap(pl):
        return [(seq[ri][0], price, peak, lab) for (ri, price, peak, lab) in pl]

    origin = (seq[anchor][0], prices[anchor], inverted)  # 下行时起点为高点(is_peak=True)
    segs = [{"kind": "impulse", "points": remap(pts), "origin": origin}]
    corr = _best_correction_from(prices, prices, Ds, end, up_to_major, corr_down=not inverted, full=True)
    if corr:
        segs.append({"kind": "correction", "points": remap(corr[0])})
    return segs


def analyze_window(highs, lows, dates, x_begin, x_end, up_to=4, anchor_cap=10, max_seg=12):
    """
    在[x_begin,x_end]窗口内做【平铺数浪】：从多个枢轴锚点分别搜索合法5浪推动(上/下行)，
    贪心选取互不重叠、跨度尽量大的一组推动铺满窗口，并在相邻推动之间填入ABC调整。
    这样整段窗口都会被标注，而不是只标一个推动。
    返回 dict: {segments:[{kind, points:[(idx,price,is_peak,label)...], origin?}], } 或 None。
    """
    n = len(highs)
    xe = min(n - 1, int(x_end))
    xb = max(0, int(x_begin))
    if xe - xb < 6:
        return None
    H = list(highs[:xe + 1])
    L = list(lows[:xe + 1])
    D = list(dates[:xe + 1])

    los, his = _pivots(H, L, xb, xe)
    los, his = _cap(los, anchor_cap), _cap(his, anchor_cap)

    cands = []  # (start, end, points, direction)
    for a in los:
        f = _best_impulse_from(H, L, D, a, up_to, down=False)
        if f:
            cands.append((a, f[1], f[0], "up"))
    for a in his:
        f = _best_impulse_from(H, L, D, a, up_to, down=True)
        if f:
            cands.append((a, f[1], f[0], "down"))
    if not cands:
        return None

    # 贪心：按跨度从大到小选互不重叠的推动
    cands.sort(key=lambda c: c[1] - c[0], reverse=True)
    chosen, occ = [], []
    for c in cands:
        s, e = c[0], c[1]
        if any(not (e <= os or s >= oe) for os, oe in occ):
            continue
        chosen.append(c)
        occ.append((s, e))
    chosen.sort(key=lambda c: c[0])

    # 组装段：推动 + 相邻推动之间尝试填ABC调整
    segments = []
    for i, (s, e, pts, dirn) in enumerate(chosen):
        origin = (s, L[s] if dirn == "up" else H[s], dirn == "down")
        segments.append({"kind": "impulse", "points": pts, "origin": origin})
        nxt_start = chosen[i + 1][0] if i + 1 < len(chosen) else xe
        f = _best_correction_from(H, L, D, e, up_to, corr_down=(dirn == "up"))
        if f and f[1] <= nxt_start:
            segments.append({"kind": "correction", "points": f[0]})

    major = _analyze_major(H, L, xb, xe, up_to)
    if not segments and not major:
        return None
    return {"minor": segments, "major": major}
