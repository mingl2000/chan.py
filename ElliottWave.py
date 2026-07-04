"""
艾略特波浪(Elliott Wave)分析：在缠论"腿"(笔/线段)骨架之上做波浪标注，
并提供跨周期(如 1d 与 15m)的分形(Fractal)一致性校验。

分形核心思想：高级别的一个推动浪(如日线第3浪)，其自身在次级别应细分为
一个5浪推动结构；高级别的一个调整浪(第2/4浪)在次级别应细分为3浪(abc)结构。
本模块利用缠论已建立的父子K线关系(CKLine_Unit.sub_kl_list / .sup_kl)把
高级别的每条腿映射到次级别对应的时间/索引区间，再对该区间内的次级别腿做
波浪分类，从而检验是否违反分形规律。

注意：艾略特数浪存在多义性(扩展浪/斜纹/变异等)，本模块给出的是"主计数+规则校验"，
是启发式判断而非唯一解；未走完的当前浪只做已完成部分的校验，不因"子浪不足"而判违规。
"""
from typing import List, Optional

from Common.CEnum import BI_DIR


# --------------------------------------------------------------------------- #
# 波浪标注(纯几何，作用于任何具有 .dir/.begin_y/.end_y 的交替方向腿序列)
# --------------------------------------------------------------------------- #
def _leg_len(lg):
    return abs(lg.end_y - lg.begin_y)


def _is_impulse(five, allow_diagonal=False) -> bool:
    """
    五条交替方向的腿是否构成合法艾略特推动浪。
    allow_diagonal=False: 严格推动，校验三条铁律(适合日线等清晰趋势)。
    allow_diagonal=True : 放宽铁律3(允许第4浪与第1浪重叠)，即容许斜纹/引导斜纹，
                          适合分钟级等重叠较多的震荡数据，否则常常一个浪都数不出来。
    """
    s = 1 if five[0].dir == BI_DIR.UP else -1  # 推动方向: +1向上 / -1向下
    for k in range(4):  # 方向必须逐段交替
        if five[k].dir == five[k + 1].dir:
            return False
    L1, L3, L5 = _leg_len(five[0]), _leg_len(five[2]), _leg_len(five[4])
    # 铁律1: 第2浪回撤不超过第1浪起点
    if s * five[1].end_y <= s * five[0].begin_y:
        return False
    # 铁律2: 第3浪不是1/3/5浪中最短的
    if L3 < L1 and L3 < L5:
        return False
    # 铁律3: 第4浪不进入第1浪价格区间(严格推动)；斜纹模式下放宽
    if not allow_diagonal and s * five[3].end_y <= s * five[0].end_y:
        return False
    return True


def _is_correction(three, prior_leg) -> bool:
    """推动之后的三条交替腿是否可作为ABC调整(宽松校验)。"""
    for k in range(2):
        if three[k].dir == three[k + 1].dir:
            return False
    return three[0].dir != prior_leg.dir  # A浪应与前一推动腿反向


def label_elliott_waves(legs, allow_diagonal=False):
    """
    在缠论腿(线段/笔)序列上贪心解析艾略特波浪。
    返回 [(leg_idx, label, kind)]，kind ∈ {'impulse','correction'}。
    识别出一个通过铁律的5浪推动后，紧随其后若存在则标注3浪ABC。
    allow_diagonal 见 _is_impulse：分钟级等震荡数据建议置True，否则常数不出浪。
    """
    labels = []
    imp = ['1', '2', '3', '4', '5']
    cor = ['A', 'B', 'C']
    i, n = 0, len(legs)
    while i < n:
        if i + 5 <= n and _is_impulse(legs[i:i + 5], allow_diagonal):
            for k in range(5):
                labels.append((i + k, imp[k], 'impulse'))
            i += 5
            if i + 3 <= n and _is_correction(legs[i:i + 3], legs[i - 1]):
                for k in range(3):
                    labels.append((i + k, cor[k], 'correction'))
                i += 3
        else:
            i += 1
    return labels


# --------------------------------------------------------------------------- #
# 跨周期分形校验
# --------------------------------------------------------------------------- #
class _Leg:
    """把缠论 CBi 适配成波浪腿视图，暴露 dir/begin_y/end_y 以及父子映射所需的KLU。"""
    __slots__ = ("bi", "dir", "is_sure", "begin_y", "end_y", "begin_klu", "end_klu", "begin_x", "end_x")

    def __init__(self, bi):
        self.bi = bi
        self.dir = bi.dir
        self.is_sure = bi.is_sure
        self.begin_y = bi.get_begin_val()
        self.end_y = bi.get_end_val()
        self.begin_klu = bi.get_begin_klu()
        self.end_klu = bi.get_end_klu()
        self.begin_x = self.begin_klu.idx
        self.end_x = self.end_klu.idx


def _legs_from_bi(bi_list) -> List[_Leg]:
    return [_Leg(bi) for bi in bi_list]


def _sub_idx_range(high_leg: _Leg):
    """高级别一条腿覆盖的次级别KLU索引区间 [lo, hi]（依赖已建立的父子关系）。"""
    begin_children = high_leg.begin_klu.sub_kl_list
    end_children = high_leg.end_klu.sub_kl_list
    if not begin_children or not end_children:
        return None
    return begin_children[0].idx, end_children[-1].idx


def _select_sub_legs(low_legs: List[_Leg], lo: int, hi: int) -> List[_Leg]:
    """取次级别中与 [lo,hi] 重叠的腿。"""
    return [lg for lg in low_legs if lg.end_x >= lo and lg.begin_x <= hi]


def _net_dir(legs: List[_Leg]):
    if not legs:
        return None
    return BI_DIR.UP if legs[-1].end_y >= legs[0].begin_y else BI_DIR.DOWN


def _find_impulse_dir(legs: List[_Leg]) -> Optional[BI_DIR]:
    """若子腿序列中存在合法5浪推动，返回其方向，否则None。"""
    labels = label_elliott_waves(legs)
    for idx, txt, kind in labels:
        if kind == 'impulse' and txt == '1':
            return legs[idx].dir
    return None


# 每个高级别浪号对应的期望子结构类型
_MOTIVE = {'1', '3', '5', 'A', 'C'}       # 推动性质：子级别应为5浪推动
_CORRECTIVE = {'2', '4', 'B'}             # 调整性质：子级别应为3浪(不应是同向5浪推动)


def validate_fractal(chan, high_idx: int = 0, low_idx: int = 1, min_sub_legs: int = 5) -> List[dict]:
    """
    校验高级别(high_idx)每条被标注的波浪腿，其次级别(low_idx)子结构是否符合分形规律。

    返回报告行列表，每行 dict 含：
      wave        高级别浪号(1..5/A..C)
      kind        motive / corrective
      dir         该浪方向
      done        该高级别腿是否已走完(is_sure)
      n_sub       落在该浪区间内的次级别腿数
      sub_type    次级别子结构判定: impulse-<dir> / corrective / insufficient / none
      status      OK / VIOLATION / INCOMPLETE / INSUFFICIENT
      note        说明
    """
    high_legs = _legs_from_bi(chan[high_idx].bi_list)
    low_legs = _legs_from_bi(chan[low_idx].bi_list)
    high_labels = label_elliott_waves(high_legs)

    rows: List[dict] = []
    for leg_idx, wave, kind in high_labels:
        hleg = high_legs[leg_idx]
        rng = _sub_idx_range(hleg)
        if rng is None:
            continue  # 该高级别腿在次级别没有覆盖数据(历史范围不重叠)，跳过
        subs = _select_sub_legs(low_legs, rng[0], rng[1])
        n_sub = len(subs)
        if n_sub == 0:
            continue  # 无重叠子腿，不纳入报告
        imp_dir = _find_impulse_dir(subs)
        is_motive = wave in _MOTIVE

        if imp_dir is not None:
            sub_type = f"impulse-{_dir_str(imp_dir)}"
        elif n_sub >= 3:
            sub_type = "corrective"
        elif n_sub >= 1:
            sub_type = "insufficient"
        else:
            sub_type = "none"

        status, note = _judge(is_motive, hleg, imp_dir, n_sub, min_sub_legs)
        rows.append(dict(wave=wave, kind='motive' if is_motive else 'corrective',
                         dir=_dir_str(hleg.dir), done=hleg.is_sure, n_sub=n_sub,
                         sub_type=sub_type, status=status, note=note))
    return rows


def _judge(is_motive, hleg, imp_dir, n_sub, min_sub_legs):
    incomplete = not hleg.is_sure
    if is_motive:
        # 推动浪：子级别应是同向5浪推动
        if imp_dir == hleg.dir:
            return "OK", "子级别为同向5浪推动，符合分形"
        if incomplete:
            return "INCOMPLETE", f"当前浪未走完，子浪进行中({n_sub}段)，暂无违规"
        if n_sub < min_sub_legs:
            return "INSUFFICIENT", f"已走完但子级别仅{n_sub}段，不足5浪推动"
        if imp_dir is not None:  # 存在推动但方向相反
            return "VIOLATION", "子级别推动方向与父浪相反"
        return "VIOLATION", "已走完但子级别未构成合法5浪推动"
    else:
        # 调整浪：子级别不应是"同向"5浪推动
        if imp_dir == hleg.dir:
            return "VIOLATION", "调整浪内含同向5浪推动，疑似父浪误判(应为推动)"
        if n_sub < 3 and not incomplete:
            return "INSUFFICIENT", f"已走完但子级别仅{n_sub}段，调整结构不足3浪"
        if incomplete:
            return "INCOMPLETE", f"当前浪未走完，子浪进行中({n_sub}段)"
        return "OK", "子级别为3浪(或反向)调整结构，符合分形"


def _dir_str(d):
    return "↑" if d == BI_DIR.UP else "↓"


def format_fractal_report(rows: List[dict], high_name: str = "high", low_name: str = "low") -> str:
    """把校验结果格式化为可读表格。"""
    if not rows:
        return f"[Fractal {high_name} vs {low_name}] 高级别未识别到艾略特波浪结构，无可校验项。"
    header = f"[Fractal Check] 高级别={high_name}  次级别={low_name}"
    line = "-" * 92
    cols = f"{'Wave':<5}{'Kind':<11}{'Dir':<4}{'Done':<6}{'#Sub':<6}{'SubStructure':<16}{'Status':<13}Note"
    out = [header, line, cols, line]
    icon = {"OK": "✓", "VIOLATION": "✗", "INCOMPLETE": "…", "INSUFFICIENT": "!"}
    for r in rows:
        out.append(
            f"{r['wave']:<5}{r['kind']:<11}{r['dir']:<4}"
            f"{('yes' if r['done'] else 'no'):<6}{r['n_sub']:<6}{r['sub_type']:<16}"
            f"{icon.get(r['status'],' ')} {r['status']:<13}{r['note']}"
        )
    out.append(line)
    violations = [r for r in rows if r['status'] == 'VIOLATION']
    if violations:
        out.append(f"结论: 发现 {len(violations)} 处分形冲突，当前数浪可能需要重新计数。")
    else:
        out.append("结论: 未发现分形冲突，各已完成波浪的次级别细分自洽。")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# 自测: 用合成腿序列验证分形判定逻辑(不依赖行情数据)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    from types import SimpleNamespace

    def leg(direction, y0, y1, sure=True):
        return SimpleNamespace(dir=direction, begin_y=y0, end_y=y1, is_sure=sure,
                               begin_x=0, end_x=0)

    UP, DOWN = BI_DIR.UP, BI_DIR.DOWN

    # 合法上行5浪推动: 1↑ 2↓ 3↑ 4↓ 5↑ (满足三条铁律)
    impulse_up = [leg(UP, 100, 120), leg(DOWN, 120, 110), leg(UP, 110, 160),
                  leg(DOWN, 160, 140), leg(UP, 140, 180)]
    # 3浪调整 a↓ b↑ c↓
    zigzag_down = [leg(DOWN, 180, 150), leg(UP, 150, 165), leg(DOWN, 165, 140)]

    print("== 波浪标注自测 ==")
    print("impulse_up ->", label_elliott_waves(impulse_up))
    print("zigzag_down ->", label_elliott_waves(zigzag_down))
    print("找到推动方向(impulse_up):", _dir_str(_find_impulse_dir(impulse_up)) if _find_impulse_dir(impulse_up) else None)

    print("\n== 分形判定自测(_judge) ==")
    cases = [
        ("推动浪↑ + 次级别同向5浪推动",  True,  leg(UP, 100, 180), UP,   5),
        ("推动浪↑ + 次级别仅3段",        True,  leg(UP, 100, 180), None, 3),
        ("推动浪↑(进行中) + 子浪3段",    True,  leg(UP, 100, 180, sure=False), None, 3),
        ("调整浪↓ + 内含同向↓5浪推动",   False, leg(DOWN, 180, 140), DOWN, 5),
        ("调整浪↓ + 反向(非同向推动)",   False, leg(DOWN, 180, 140), UP,   3),
    ]
    for desc, is_motive, hleg, imp_dir, n_sub in cases:
        status, note = _judge(is_motive, hleg, imp_dir, n_sub, min_sub_legs=5)
        print(f"  {desc:<32} -> {status:<12} | {note}")
