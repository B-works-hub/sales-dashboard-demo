# -*- coding: utf-8 -*-
"""가상 주문 원장 — 월간 리포트 5종의 유일한 진실.

리포트를 따로 만들면 판매처별의 '자사몰 7월'과 Chart 의 '자사몰 7월'이
어긋납니다. 그래서 원장을 한 번만 만들고 리포트는 전부 여기서 집계합니다.

원장은 커밋하지 않습니다. build_*.py 가 메모리에서 받아 집계 결과만
data/*.js 로 씁니다 — 원장을 그대로 실으면 파일 하나가 수 MB 가 됩니다.

난수는 고정 시드입니다. 같은 코드는 항상 같은 원장을 만듭니다.
"""

import random
import datetime as dt

import master as M

SEED = 20260714

# 주문 라인 한 줄의 모양
FIELDS = ('date', 'order', 'cust', 'member', 'age', 'channel',
          'sku', 'line', 'qty', 'amount', 'gift', 'subs', 'nation', 'hour',
          'dest')


class Row(object):
    __slots__ = FIELDS

    def __init__(self, **kw):
        for f in FIELDS:
            setattr(self, f, kw.get(f))

    def ym(self):
        return (self.date.year, self.date.month)


# ── 모양 잡기 ───────────────────────────────────────────────────────
# 난수만 뿌리면 그래프가 톱니처럼 보이고 증감률이 의미 없는 값이 됩니다.
# 계절성·성장·기획전을 넣어 읽을 수 있는 모양을 만듭니다.

MONTH_SEASON = {            # 월별 계수 — 12월 선물 시즌, 여름 비수기
    1: 0.95, 2: 0.86, 3: 1.10, 4: 1.18, 5: 1.02, 6: 0.88,
    7: 0.84, 8: 0.90, 9: 1.05, 10: 1.08, 11: 1.12, 12: 1.35,
}

WEEKDAY_SEASON = [1.10, 1.06, 1.04, 1.02, 1.12, 0.86, 0.80]   # 월~일

# 장바구니 계절성. 이걸 빼면 객단가가 ±4% 안에서만 움직여, 월별 증감률
# 지표가 전부 0% 근처로 뭉개집니다. 선물 시즌에는 여러 개를 한 번에 삽니다.
BASKET_SEASON = {
    1: 1.02, 2: 0.94, 3: 1.08, 4: 1.14, 5: 1.00, 6: 0.88,
    7: 0.86, 8: 0.92, 9: 1.04, 10: 1.06, 11: 1.16, 12: 1.34,
}

PROMOS = [   # (시작, 종료, 배수, 라벨)
    ((2025, 3, 21), (2025, 3, 30), 1.6, '봄맞이 홈프래그런스'),
    ((2025, 6,  5), (2025, 6, 11), 1.4, '핸드케어 위크'),
    ((2025, 11, 24), (2025, 11, 30), 1.9, '연말 기프트 위크'),
    ((2026, 3, 30), (2026, 4,  3), 2.1, '빅 기프트 이벤트'),
    ((2026, 7, 23), (2026, 7, 31), 1.5, '룸스프레이 신규 런칭'),
]


def _growth(ym):
    """기준월까지 완만히 성장. 2025.11 수출 개시로 한 단 뜁니다."""
    i = M.ALL_MONTHS.index(ym)
    g = 1.0 + 0.006 * i
    if ym >= (2025, 11):
        g *= 1.18
    return g


def _promo_mult(d):
    for (s, e, mult, _) in PROMOS:
        if dt.date(*s) <= d <= dt.date(*e):
            return mult
    return 1.0


def _weighted(rng, items, weights):
    t = sum(weights)
    x = rng.random() * t
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if x <= acc:
            return it
    return items[-1]


# ── 고객 풀 ─────────────────────────────────────────────────────────

class Customer(object):
    __slots__ = ('key', 'member', 'age', 'loyalty', 'subs', 'joined')

    def __init__(self, key, member, age, loyalty, subs, joined):
        self.key = key
        self.member = member
        self.age = age
        self.loyalty = loyalty     # 재구매 성향 0~1
        self.subs = subs           # 정기배송 이용자
        self.joined = joined       # 첫 등장 월


def _build_customers(rng, n=30000):
    """풀을 넉넉히 만들어 두고 월마다 일부만 활성화합니다.

    충성도는 한쪽으로 크게 쏠려 있어야 합니다. 고르게 주면 모두가 한 번씩만
    사고 사라져 재구매 비중이 절반에도 못 미치고, 반대로 이탈만 쌓입니다.
    """
    out = []
    for i in range(n):
        member = rng.random() < 0.83
        age = _weighted(rng, M.AGE_BANDS, M.AGE_MIX)
        loyalty = min(1.0, max(0.0, rng.gauss(0.50, 0.30)))
        subs = member and rng.random() < 0.035
        joined = M.ALL_MONTHS[rng.randrange(len(M.ALL_MONTHS))]
        out.append(Customer('C%06d' % i, member, age, loyalty, subs, joined))
    return out


# ── 원장 ────────────────────────────────────────────────────────────

BASE_ORDERS = 900.0   # 보정 전 기준 월 주문 수. build_calibrated() 가 조정합니다.


def build(scale=1.0):
    # 고객 풀은 scale 과 무관하게 고정입니다.
    customers = _build_customers(random.Random(SEED))
    rows = []
    order_no = 0

    chan_open, chan_close = {}, {}
    for c in M.CHANNELS:
        y, mo = [int(x) for x in c['opened'].split('.')]
        chan_open[c['key']] = (y, mo)
        if c['closed']:
            y, mo = [int(x) for x in c['closed'].split('.')]
            chan_close[c['key']] = (y, mo)

    line_codes   = [l['code'] for l in M.LINES]
    line_weights = [l['weight'] for l in M.LINES]
    # 단품과 세트를 따로 담습니다. 한 바구니에서 뽑으면 세트가 라인마다
    # 개수가 달라 비중이 라인 가중치와 어긋납니다.
    single_by_line, bundle_by_line = {}, {}
    for s in M.SINGLES:
        single_by_line.setdefault(s['line'], []).append(s)
    for s in M.BUNDLES:
        bundle_by_line.setdefault(s['line'], []).append(s)

    for ym in M.ALL_MONTHS:
        # 그 달에 열려 있는 채널만 — 종료한 채널은 종료월까지만 팝니다.
        open_ch = [c for c in M.CHANNELS
                   if chan_open[c['key']] <= ym
                   and ym <= chan_close.get(c['key'], (9999, 12))]
        ch_w = [c['freq'] for c in open_ch]
        if not sum(ch_w):
            continue

        base = BASE_ORDERS * scale * MONTH_SEASON[ym[1]] * _growth(ym)
        ndays = M.days_in_month(ym)

        # 그 달에 살아 있는 고객 (가입 이후)
        pool = [c for c in customers if c.joined <= ym]
        if not pool:
            continue

        for day in range(1, ndays + 1):
            # 날짜마다 독립 시드. 하나의 전역 시퀀스를 쓰면 scale 을 조금만
            # 바꿔도 난수 호출 횟수가 달라져 뒤의 모든 날이 뒤틀리고,
            # 보정이 수렴하지 않고 ±5% 로 진동합니다.
            rng = random.Random(SEED * 1000000 + ym[0] * 10000 + ym[1] * 100 + day)
            d = dt.date(ym[0], ym[1], day)
            daily = base / ndays
            daily *= WEEKDAY_SEASON[d.weekday()]
            daily *= _promo_mult(d)
            n_orders = int(round(rng.gauss(daily, daily * 0.12)))
            if n_orders < 0:
                n_orders = 0

            for _ in range(n_orders):
                cust = pool[rng.randrange(len(pool))]
                # 충성 고객일수록 자주 다시 등장 — 재구매 지표가 살아납니다
                # 충성 고객일수록 다시 뽑힐 확률이 높습니다. 제곱을 써서
                # 상위 고객으로 기울입니다 — 선형이면 재구매가 안 살아납니다.
                if rng.random() > cust.loyalty ** 2:
                    continue

                ch = _weighted(rng, open_ch, ch_w)
                order_no += 1
                oid = 'O%s%05d' % (d.strftime('%y%m%d'), order_no % 100000)
                gift = rng.random() < (0.22 if ym[1] == 12 else 0.09)
                nation = None
                hour = None
                dest = None
                if ch['key'] == '수출':
                    dest = _weighted(rng, M.EXPORT_NATIONS,
                                     [0.34, 0.26, 0.18, 0.12, 0.10])
                if ch['key'] == '플래그십':
                    # 매장은 외국인 비중이 높고 해마다 오릅니다
                    foreign = rng.random() < (0.30 + 0.10 * (ym[0] - 2024))
                    nation = (_weighted(rng, M.NATIONS,
                                        [0.42, 0.16, 0.14, 0.10, 0.06, 0.12])
                              if foreign else '내국인')
                    hour = M.HOURS[min(len(M.HOURS) - 1,
                                       int(abs(rng.gauss(4.5, 2.4))))]

                bk = BASKET_SEASON[ym[1]] * _promo_mult(d) ** 0.35
                n_lines = 1 + (rng.random() < 0.30 * bk) + (rng.random() < 0.06 * bk)
                picked = set()
                for _ in range(n_lines):
                    code = _weighted(rng, line_codes, line_weights)
                    if code in picked:
                        continue
                    picked.add(code)
                    # 세트는 선물 시즌과 기프트 주문에서 더 자주 나갑니다.
                    sku_pool = single_by_line[code]
                    if bundle_by_line.get(code):
                        p_bundle = 0.34 if gift else (0.22 if ym[1] == 12 else 0.14)
                        if rng.random() < p_bundle:
                            sku_pool = bundle_by_line[code]
                    sku = sku_pool[rng.randrange(len(sku_pool))]
                    qty = 1 + (rng.random() < 0.20 * bk) + (rng.random() < 0.04 * bk)
                    if ch['bulk'] > 1:
                        # 건당 수량 배수. 평균이 bulk 가 되도록 ±40% 로 흔듭니다.
                        qty *= max(1, int(round(ch['bulk'] * rng.uniform(0.6, 1.4))))
                    rows.append(Row(
                        date=d, order=oid, cust=cust.key, member=cust.member,
                        age=cust.age, channel=ch['key'], sku=sku['sku'],
                        line=code, qty=qty, amount=qty * sku['price'],
                        gift=gift or sku['is_gift'], subs=cust.subs,
                        nation=nation, hour=hour, dest=dest,
                    ))

    return rows, customers


def annual_krw(rows, year_end=M.BASE_MONTH):
    """기준월까지 직전 12개월 매출. 보정 기준입니다."""
    window = set(M.month_range(M.shift_month(year_end, -11), year_end))
    return sum(r.amount for r in rows if r.ym() in window)


def build_calibrated(tol=0.005, max_pass=6, verbose=False):
    """목표 연매출에 맞춰 주문 수를 반복 보정합니다.

    금액을 사후에 곱해 맞추면 정가 × 수량이 깨져 표의 검산이 안 됩니다.
    그래서 '주문 수'를 조정하고 가격은 마스터 그대로 둡니다.

    주문 수를 늘리면 같은 고객이 다시 뽑힐 확률이 함께 움직이기 때문에
    한 번 나눠서는 맞지 않습니다. 허용 오차에 들어올 때까지 돕니다.
    """
    scale = 1.0
    rows = custs = None
    for i in range(1, max_pass + 1):
        rows, custs = build(scale)
        got = annual_krw(rows)
        err = (got - M.TARGET_ANNUAL_KRW) / float(M.TARGET_ANNUAL_KRW)
        if verbose:
            print('  보정 %d회 : scale=%.4f  연매출 %s  오차 %+.2f%%'
                  % (i, scale, format(got, ','), err * 100))
        if abs(err) <= tol:
            break
        scale *= M.TARGET_ANNUAL_KRW / float(got)
    else:
        raise AssertionError('연매출 보정이 %d회 안에 수렴하지 않았습니다' % max_pass)
    return rows, custs


# ── 파생 시리즈 ─────────────────────────────────────────────────────
# 원장에 없는 것들 — 방문 수, 신규 회원 가입, 매장 방문객 —은 원장과
# 같은 시드에서 따로 만들되 매출 모양을 따라가게 둡니다.

def traffic(rows):
    """자사몰 월별 방문 수 / 신규 회원 수."""
    rng = random.Random(SEED + 1)
    by_m = {}
    for r in rows:
        if r.channel == '자사몰':
            by_m[r.ym()] = by_m.get(r.ym(), 0) + r.amount
    out = {}
    for ym in M.ALL_MONTHS:
        rev = by_m.get(ym, 0)
        visits = int(rev / 3200 * rng.uniform(0.85, 1.15)) + 4200
        signup = int(visits * rng.uniform(0.025, 0.045))
        out[ym] = dict(visits=visits, signup=signup)
    return out


# 시간대별 방문 곡선 — 점심과 늦은 오후에 몰립니다. 합이 1 입니다.
HOUR_CURVE = [.055, .075, .125, .115, .130, .125, .110, .095, .100, .070]

# 요일 계수 — 주말 매장은 평일보다 붐빕니다(온라인과 반대 방향입니다).
STORE_WEEKDAY = [0.82, 0.86, 0.90, 0.95, 1.18, 1.42, 1.30]   # 월~일

# 방문객 ÷ 구매건수. 매장은 안 사고 나가는 사람이 훨씬 많습니다.
# 구매 없는 시간대의 통행량을 정합니다. 슬롯 전환율(conv)과 함께
# 전체 전환율을 결정합니다 — 2.4 면 23%, 0.6 면 38% 근처입니다.
VISITOR_RATIO = 0.60


def store_traffic(rows):
    """플래그십 방문객 — 날짜 × 시간대 × 내/외국인.

    구매가 있었던 슬롯에만 방문객을 만들면 시간대별 표가 듬성듬성해지고,
    '그 시간에 아무도 안 왔다' 와 '왔지만 안 샀다' 가 같은 칸이 됩니다.
    영업일 × 시간대 × 내/외국인 전 슬롯을 만들고, 구매건수는 원장에서
    그대로 가져옵니다 — 두 값이 어긋나면 전환율이 거짓이 됩니다.

    방문객은 '기본 통행량' 과 '구매건수 ÷ 목표전환율' 중 큰 쪽입니다.
    구매건수보다 작은 방문객은 전환율 100%% 초과를 만듭니다.

    시드는 슬롯마다 독립입니다. 전역 시퀀스 하나를 쓰면 원장이 조금만
    달라져도 모든 슬롯의 전환율이 뒤틀립니다.
    """
    orders = {}
    open_from = None
    for r in rows:
        if r.channel != '플래그십':
            continue
        if open_from is None or r.date < open_from:
            open_from = r.date
        key = (r.date, r.hour, r.nation != '내국인')
        orders.setdefault(key, set()).add(r.order)
        # 국적은 주문 단위로 하나입니다
    if open_from is None:
        return {}

    # 매장 규모 — 원장의 플래그십 주문 수에 맞춰 기본 통행량을 정합니다.
    n_orders = len(set(o for s in orders.values() for o in s))
    n_days = len(set(d for (d, _, _) in orders))
    per_day = (n_orders / float(n_days)) if n_days else 10.0

    out = {}
    last = max(d for (d, _, _) in orders)
    day = open_from
    while day <= last:
        wk = STORE_WEEKDAY[day.weekday()]
        for hi, hour in enumerate(M.HOURS):
            for foreign in (True, False):
                rng = random.Random('%d|%s|%d|%d' % (SEED, day.isoformat(), hi, foreign))
                bought = len(orders.get((day, hour, foreign), ()))
                # 외국인 방문 비중은 해마다 오릅니다(원장의 국적 배정과 같은 방향).
                fshare = 0.27 + 0.08 * (day.year - 2024)
                share = fshare if foreign else (1 - fshare)
                base = per_day * VISITOR_RATIO * wk * HOUR_CURVE[hi] * share
                base = max(0, int(round(rng.gauss(base, base * 0.35))))
                conv = rng.uniform(0.28, 0.56)   # 슬롯 전환율 — 평균 42%
                need = int(round(bought / conv)) if bought else 0
                visitors = max(base, need, bought)
                if not visitors:
                    continue
                out.setdefault((day.year, day.month), []).append(dict(
                    date=day, hour=hour, foreign=foreign,
                    visitors=visitors, orders=bought))
        day += dt.timedelta(days=1)
    return out


def selftest():
    rows, customers = build_calibrated(verbose=True)
    assert rows, '원장이 비었습니다'
    months = sorted(set(r.ym() for r in rows))
    assert months[0] == M.LEDGER_START, months[0]
    assert months[-1] == M.BASE_MONTH, months[-1]
    chans = set(r.channel for r in rows)
    missing = [n for n in M.DAILY_CHANNEL_NAMES if n not in chans]
    assert not missing, '원장에 없는 판매처: %s' % missing
    assert any(r.channel == '플래그십' and r.nation for r in rows), '플래그십 국적 없음'
    # 종료한 채널은 종료월 이후 주문이 없어야 합니다
    for c in M.CHANNELS:
        if not c['closed']:
            continue
        cy, cm = [int(x) for x in c['closed'].split('.')]
        after = [r for r in rows if r.channel == c['key'] and r.ym() > (cy, cm)]
        assert not after, '%s: 종료월 이후 주문 %d건' % (c['key'], len(after))

    ann = annual_krw(rows)
    err = abs(ann - M.TARGET_ANNUAL_KRW) / float(M.TARGET_ANNUAL_KRW)
    assert err < 0.02, '연매출 보정 오차 %.1f%%' % (err * 100)

    by_ch = {}
    for r in rows:
        by_ch[r.channel] = by_ch.get(r.channel, 0) + r.amount
    tot = float(sum(by_ch.values()))
    share = dict((k, round(v / tot, 4)) for k, v in by_ch.items())
    aov = sum(r.amount for r in rows) / float(len(set(r.order for r in rows)))
    own = [r for r in rows if r.channel == '자사몰']
    aov_own = sum(r.amount for r in own) / float(len(set(r.order for r in own)))
    return dict(rows=len(rows), orders=len(set(r.order for r in rows)),
                months=len(months), channels=len(chans),
                customers=len(set(r.cust for r in rows)),
                annual_krw=ann, aov_all=int(aov), aov_자사몰=int(aov_own),
                top_share=sorted(share.items(), key=lambda kv: -kv[1])[:6])


if __name__ == '__main__':
    import pprint
    pprint.pprint(selftest())
