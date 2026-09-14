# -*- coding: utf-8 -*-
"""상품별 리포트 — 원장 → data/product.js

제품라인 14종 각각에 대해 같은 지표를 냅니다.

  경험 : 이 라인을 산 고객이 전체 구매 고객의 몇 %인가 (당월 / 12개월)
  유입 : 그 중 몇 명이 이 라인을, 또는 브랜드 자체를 처음 샀는가
  유지 : 몇 명이 다시 샀는가 · 주기 · 횟수
  연결 : 본품을 산 사람이 리필까지 갔는가
  구성 : 연령대

고객 리포트와 달리 **고객 식별이 가능한 채널 전체**를 봅니다 — 대량주문·
어매니티·수출은 받는 쪽이 법인이라 '이 사람이 이 라인을 경험했다'를 셀 수
없습니다. 그래서 두 리포트의 분모가 다릅니다. 화면 각주에 적습니다.
"""

import os
import statistics

import master as M
import ledger as L
import reportlib as R

OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'product.js')
LOOKBACK = 12


def _index(rows):
    """식별 가능 채널의 주문을 접습니다.

    all_m[ym]            그 달에 산 고객 전체
    line_m[code][ym]     그 달에 그 라인을 산 고객
    dates[code][ym][c]   그 달 그 라인을 산 날짜들 (재구매 주기용)
    age[ym][c]           연령대
    val[code][ym]        라인 매출 · qty[code][ym] 수량
    refill_m[code][ym]   그 달 그 라인의 '리필' SKU 를 산 고객
    """
    ok = set(M.IDENTIFIED_CHANNELS)
    all_m, line_m, dates, age = {}, {}, {}, {}
    val, qty, refill_m = {}, {}, {}
    for r in rows:
        if r.channel not in ok:
            continue
        ym = r.ym()
        all_m.setdefault(ym, set()).add(r.cust)
        age.setdefault(ym, {})[r.cust] = r.age
        line_m.setdefault(r.line, {}).setdefault(ym, set()).add(r.cust)
        dates.setdefault(r.line, {}).setdefault(ym, {}).setdefault(r.cust, set()).add(r.date)
        val.setdefault(r.line, {})[ym] = val.setdefault(r.line, {}).get(ym, 0) + r.amount
        qty.setdefault(r.line, {})[ym] = qty.setdefault(r.line, {}).get(ym, 0) + r.qty
        if M.SKU_BY_CODE[r.sku]['is_refill']:
            refill_m.setdefault(r.line, {}).setdefault(ym, set()).add(r.cust)
    return dict(all_m=all_m, line_m=line_m, dates=dates, age=age,
                val=val, qty=qty, refill_m=refill_m)


def _union(by_ym, ym, back=LOOKBACK, include_self=True):
    out = set()
    for k in (range(0, back) if include_self else range(1, back + 1)):
        out |= by_ym.get(M.shift_month(ym, -k), set())
    return out


def _first_seen(ix):
    """고객이 '처음' 산 시점 — 브랜드 전체 / 라인별.

    12개월 창 기준의 첫구매는 '창 안에 샀고, 창 이전에는 산 적이 없다' 입니다.
    창 이전 누적 집합을 매달 다시 만들면 창을 뺀 집합에서 창 원소를 찾는
    실수를 하기 쉽습니다(그러면 분자가 분모와 같아져 늘 100%% 가 됩니다).
    최초 구매월을 한 번 구해 두고 창 시작월과 비교합니다.
    """
    brand, line = {}, {}
    for ym in sorted(ix['all_m']):
        for c in ix['all_m'][ym]:
            if c not in brand:
                brand[c] = ym
    for code, by in ix['line_m'].items():
        d = line.setdefault(code, {})
        for ym in sorted(by):
            for c in by[ym]:
                if c not in d:
                    d[c] = ym
    return brand, line


def _line_rows(code, ix, months, calc_months, first_brand, first_line):
    line = M.LINE_BY_CODE[code]
    lm   = ix['line_m'].get(code, {})
    rf   = ix['refill_m'].get(code, {})
    dts  = ix['dates'].get(code, {})

    a = dict((k, {}) for k in (
        'exp_m', 'exp_m_den', 'first_line_m',
        'exp_y', 'exp_y_den', 'first_brand_y', 'first_line_y',
        'repeat_y', 'cycle', 'rep_avg', 'rep_med', 'rep_max',
        'refill', 'refill_den', 'winback', 'val', 'qty'))
    ages = dict((x, {}) for x in M.AGE_BANDS)

    ever_line, ever_brand, gone_prev = set(), set(), set()

    for ym in calc_months:
        cur_line = lm.get(ym, set())
        cur_all  = ix['all_m'].get(ym, set())

        # 당월 기준
        a['exp_m'][ym]     = len(cur_line)
        a['exp_m_den'][ym] = len(cur_all)
        a['first_line_m'][ym] = len(cur_line - ever_line)

        # 12개월 기준 (당월 포함)
        win_line = _union(lm, ym)
        win_all  = _union(ix['all_m'], ym)
        a['exp_y'][ym]     = len(win_line)
        a['exp_y_den'][ym] = len(win_all)

        # 12개월 창 기준 첫구매 — 창 안에 샀고, 최초 구매가 창 안인 고객.
        # 최초 구매가 창보다 앞이면 그 창에서는 '첫구매' 가 아닙니다.
        win_start = M.shift_month(ym, -(LOOKBACK - 1))
        fl = first_line.get(code, {})
        a['first_line_y'][ym]  = len([c for c in win_line
                                      if fl.get(c, ym) >= win_start])
        a['first_brand_y'][ym] = len([c for c in win_line
                                      if first_brand.get(c, ym) >= win_start])

        # 재구매 — 12개월 창 안에서 그 라인을 2회 이상 산 고객
        counts, cycles = [], []
        for c in win_line:
            ds = set()
            for k in range(0, LOOKBACK):
                ds |= dts.get(M.shift_month(ym, -k), {}).get(c, set())
            if len(ds) < 2:
                continue
            ds = sorted(ds)
            counts.append(len(ds))
            gaps = [(b - x).days for x, b in zip(ds, ds[1:])]
            cycles.append(sum(gaps) / float(len(gaps)))
        a['repeat_y'][ym] = len(counts)
        a['cycle'][ym]    = (sum(cycles) / len(cycles)) if cycles else None
        a['rep_avg'][ym]  = (sum(counts) / float(len(counts))) if counts else None
        a['rep_med'][ym]  = statistics.median(counts) if counts else None
        a['rep_max'][ym]  = max(counts) if counts else None

        # 리필 구매 연결 — 12개월 창에서 이 라인을 산 사람 중 리필까지 간 사람
        if line['refill']:
            win_rf = _union(rf, ym)
            a['refill'][ym]     = len(win_line & win_rf)
            a['refill_den'][ym] = len(win_line)

        # 이탈 후 재구매 — 12개월 이상 이 라인을 안 사다가 당월 다시 산 고객
        a['winback'][ym] = len(cur_line & gone_prev)
        gone_prev = ever_line - win_line

        a['val'][ym] = ix['val'].get(code, {}).get(ym, 0)
        a['qty'][ym] = ix['qty'].get(code, {}).get(ym, 0)

        ages_ym = ix['age'].get(ym, {})
        for band in M.AGE_BANDS:
            ages[band][ym] = len([c for c in cur_line if ages_ym.get(c) == band])

        ever_line  |= cur_line
        ever_brand |= cur_all

    K = R
    metrics = [
        R.ratio_row('경험률(당월)', a['exp_m'], a['exp_m_den'],
                    '당월 이 라인을 산 고객 ÷ 당월 전체 구매 고객'),
        R.row('경험고객수(당월)', K.KIND_INT, a['exp_m']),
        R.ratio_row('해당라인 첫구매율(당월)', a['first_line_m'], a['exp_m'],
                    '이 라인을 처음 산 고객 ÷ 당월 이 라인 구매 고객'),
        R.row('해당라인 첫구매고객수(당월)', K.KIND_INT, a['first_line_m']),
        R.ratio_row('경험률(12개월)', a['exp_y'], a['exp_y_den'],
                    '직전 12개월 이 라인을 산 고객 ÷ 같은 기간 전체 구매 고객'),
        R.row('경험고객수(12개월)', K.KIND_INT, a['exp_y']),
        R.ratio_row('브랜드 첫구매율(12개월)', a['first_brand_y'], a['exp_y'],
                    '이 라인 구매 고객 중 브랜드 자체가 첫 구매인 고객의 비중'),
        R.row('브랜드 첫구매고객수(12개월)', K.KIND_INT, a['first_brand_y']),
        R.ratio_row('해당라인 첫구매율(12개월)', a['first_line_y'], a['exp_y']),
        R.row('해당라인 첫구매고객수(12개월)', K.KIND_INT, a['first_line_y']),
        R.ratio_row('재구매율(12개월)', a['repeat_y'], a['exp_y'],
                    '직전 12개월 안에 이 라인을 2회 이상 산 고객의 비중'),
        R.row('재구매고객수(12개월)', K.KIND_INT, a['repeat_y']),
        R.row('재구매주기', K.KIND_DAYS, a['cycle'],
              '2회 이상 산 고객의 구매 간격 평균(일)'),
        R.row('재구매횟수(avg)', K.KIND_FLOAT, a['rep_avg']),
        R.row('재구매횟수(median)', K.KIND_FLOAT, a['rep_med']),
        R.row('최대 재구매 횟수', K.KIND_INT, a['rep_max']),
    ]
    if line['refill']:
        metrics += [
            R.ratio_row('리필구매연결비율', a['refill'], a['refill_den'],
                        '이 라인을 산 고객 중 리필 제품까지 산 고객의 비중'),
            R.row('리필구매연결고객수', K.KIND_INT, a['refill']),
        ]
    metrics += [
        R.row('이탈후 재구매', K.KIND_INT, a['winback'],
              '12개월 이상 이 라인을 사지 않다가 당월 다시 산 고객'),
        R.row('라인 매출', K.KIND_KRW, a['val'], '식별 가능 채널 기준'),
        R.row('판매수량', K.KIND_INT, a['qty']),
    ]

    age_rows = []
    for band in M.AGE_BANDS:
        age_rows.append(R.row(band, K.KIND_INT, ages[band]))
        age_rows.append(R.ratio_row('(비중)', ages[band], a['exp_m']))
    age_rows.append(R.row('총합계', K.KIND_INT, a['exp_m']))

    cur_den = a['exp_m_den'].get(months[-1]) or 0
    cur_n   = a['exp_m'].get(months[-1]) or 0
    return dict(
        code=code, name=line['name'], cat=line['cat'], refill=line['refill'],
        buyers=cur_n, thin=(cur_n < R.MIN_DEN),
        sections=[
            dict(key='metric', label='라인 지표', rows=metrics),
            dict(key='age',    label='구매 연령대', rows=age_rows),
        ],
    )


def build(rows, customers):
    ix = _index(rows)
    months = M.WINDOW_13
    calc_months = M.month_range(M.shift_month(months[0], -12), months[-1])

    first_brand, first_line = _first_seen(ix)
    lines = {}
    for line in M.LINES:
        lines[line['code']] = _line_rows(line['code'], ix, months, calc_months,
                                         first_brand, first_line)

    # 라인 비교 — 14줄을 한 장에 놓습니다. 개별 라인 탭만 있으면
    # '어느 라인이 크고 어느 라인이 줄고 있는가'를 볼 수가 없습니다.
    all_m = ix['all_m']
    ov_exp, ov_val = [], []
    for line in M.LINES:
        code = line['code']
        lm = ix['line_m'].get(code, {})
        exp = dict((ym, len(lm.get(ym, set()))) for ym in calc_months)
        ov_exp.append(R.ratio_row('%s %s' % (code, line['name']), exp,
                                  dict((ym, len(all_m.get(ym, set()))) for ym in calc_months)))
        ov_val.append(R.row('%s %s' % (code, line['name']), R.KIND_KRW,
                            ix['val'].get(code, {})))

    overview = [
        dict(key='exp', label='라인별 경험률(당월)', rows=ov_exp),
        dict(key='val', label='라인별 매출',         rows=ov_val),
    ]

    return dict(
        title='상품별 리포트',
        base=M.month_key(M.BASE_MONTH),
        channel='고객 식별 가능 채널 %d곳' % len(M.IDENTIFIED_CHANNELS),
        months=R.month_labels(),
        categories=[dict(name=c, lines=[l['code'] for l in M.LINES if l['cat'] == c])
                    for c in M.CATEGORIES],
        lines=lines,
        overview=overview,
        min_den=R.MIN_DEN,
        notes=[
            '고객 식별이 가능한 채널만 봅니다 — 대량주문·사입·어매니티·면세·수출은 '
            '받는 쪽이 법인이거나 중간 유통이라 사람 단위로 셀 수 없습니다. '
            '고객 리포트(자사몰 기준)와 분모가 다릅니다.',
            '한 달 구매 고객이 %d명 미만인 칸은 비율을 내지 않고 비웁니다 — '
            '3명 중 2명이 재구매하면 66.7%%로 찍히는데, 신호가 아니라 잡음입니다.'
            % R.MIN_DEN,
            '비중 지표의 증감은 %p 로, 금액·수량 지표의 증감은 % 로 냅니다.',
        ],
    )


def check(payload):
    """조용히 틀린 비율을 잡습니다.

    분자와 분모를 잘못 짝지으면 비율이 전 기간 정확히 100%% 로 눕습니다.
    표에서는 그냥 '경험률이 높은 라인' 처럼 보여서 눈으로는 안 걸립니다.
    """
    bad = []
    groups = [('overview', payload['overview'])]
    for code, v in payload['lines'].items():
        groups.append((code, v['sections']))
    for who, sections in groups:
        for sec in sections:
            for r in sec['rows']:
                if r['kind'] != 'pct':
                    continue
                got = [v for v in r['values'] if v is not None]
                if len(got) >= 3 and all(abs(v - 1.0) < 1e-9 for v in got):
                    bad.append('%s / %s' % (who, r['name']))
    assert not bad, '비율이 전 기간 100%% 입니다 — 분자·분모를 확인하세요:\n  ' \
                    + '\n  '.join(bad)

    # 불변식 : 브랜드가 처음인 고객은 그 라인도 반드시 처음입니다.
    # 따라서 브랜드 첫구매 고객수는 해당라인 첫구매 고객수를 넘을 수 없습니다.
    for code, v in payload['lines'].items():
        byname = {}
        for sec in v['sections']:
            for r in sec['rows']:
                byname[r['name']] = r
        b = byname['브랜드 첫구매고객수(12개월)']['values']
        l = byname['해당라인 첫구매고객수(12개월)']['values']
        for i in range(len(b)):
            if b[i] is None or l[i] is None:
                continue
            assert b[i] <= l[i], (
                '%s %d번째 달: 브랜드 첫구매 %d > 해당라인 첫구매 %d'
                % (code, i, b[i], l[i]))
    return len(bad)


def main():
    rows, customers = L.build_calibrated()
    payload = build(rows, customers)
    check(payload)
    out = os.path.abspath(OUT)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    n = R.js_file(out, 'PRODUCT_DATA', payload, payload['title'])
    thin = [c for c, v in payload['lines'].items() if v['thin']]
    print('data/product.js  %s bytes  (라인 %d · 표본 부족 %s)'
          % (format(n, ','), len(payload['lines']), thin or '없음'))


if __name__ == '__main__':
    main()
