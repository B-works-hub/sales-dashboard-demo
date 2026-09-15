# -*- coding: utf-8 -*-
"""플래그십 리포트 — 원장 → data/flagship.js

매장 하나를 세 축으로 봅니다.

    요일  ×  시간대  ×  내/외국인(국적 6)

원본은 월마다 탭을 하나씩 두고 그 안에 요일·시간대를 세로로 깔았습니다.
탭이 아홉 장이라 '지난달보다 목요일이 늘었나' 를 보려면 탭을 오가야 합니다.
여기서는 축을 뒤집어, 요일과 시간대를 행에 두고 13개월을 가로로 폅니다 —
나머지 네 리포트와 같은 문법이고, 추이가 한 화면에 들어옵니다.

방문객은 원장에 없습니다. 매장에 들어왔지만 사지 않은 사람은 주문을
남기지 않기 때문입니다. ledger.store_traffic() 이 영업일 × 시간대 ×
내/외국인 전 슬롯에 방문객을 만들고, **구매건수는 원장에서 그대로**
가져옵니다 — 두 값이 서로 다른 데서 오면 전환율이 거짓이 됩니다.
"""

import os

import master as M
import ledger as L
import reportlib as R

OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'flagship.js')
CHANNEL = '플래그십'

MEASURES = [
    dict(key='visitors', label='방문객',     kind=R.KIND_INT),
    dict(key='orders',   label='구매건수',   kind=R.KIND_INT),
    dict(key='amount',   label='매출액',     kind=R.KIND_KRW),
    dict(key='conv',     label='구매전환율', kind=R.KIND_PCT),
]
AUDIENCES = [dict(key='all', label='전체'),
             dict(key='foreign', label='외국인'),
             dict(key='local', label='내국인')]


def _index(rows, traffic):
    """월 × 요일/시간대 × 대상 으로 접습니다.

    방문객은 traffic 에서, 구매건수·매출은 원장에서 옵니다. 구매건수를
    traffic 쪽 값으로 쓰면 매출과 분모가 어긋납니다.
    """
    # 주문 단위로 국적·시간을 확정합니다 — 한 주문의 라인들은 같은 값입니다.
    order_meta, order_amt = {}, {}
    for r in rows:
        if r.channel != CHANNEL:
            continue
        order_meta[r.order] = (r.date, r.hour, r.nation)
        order_amt[r.order] = order_amt.get(r.order, 0) + r.amount

    buy = {}      # (ym, axis, key, aud) -> dict(orders, amount)
    def add(ym, axis, key, aud, amt):
        d = buy.setdefault((ym, axis, key, aud), dict(orders=0, amount=0))
        d['orders'] += 1
        d['amount'] += amt

    for oid, (date, hour, nation) in order_meta.items():
        ym = (date.year, date.month)
        amt = order_amt[oid]
        foreign = nation != '내국인'
        auds = ['all', 'foreign' if foreign else 'local']
        wd = M.WEEKDAYS[date.weekday()]
        for aud in auds:
            add(ym, 'weekday', wd, aud, amt)
            add(ym, 'hour', hour, aud, amt)
            add(ym, 'total', '합계', aud, amt)
        add(ym, 'nation', nation, 'all', amt)

    vis = {}      # (ym, axis, key, aud) -> 방문객
    def addv(ym, axis, key, aud, n):
        vis[(ym, axis, key, aud)] = vis.get((ym, axis, key, aud), 0) + n

    for ym, slots in traffic.items():
        for s in slots:
            auds = ['all', 'foreign' if s['foreign'] else 'local']
            wd = M.WEEKDAYS[s['date'].weekday()]
            for aud in auds:
                addv(ym, 'weekday', wd, aud, s['visitors'])
                addv(ym, 'hour', s['hour'], aud, s['visitors'])
                addv(ym, 'total', '합계', aud, s['visitors'])

    days = {}     # ym -> 영업일 수 (일평균용)
    for ym, slots in traffic.items():
        days[ym] = len(set(s['date'] for s in slots))
    return buy, vis, days


def _val(buy, vis, ym, axis, key, aud, measure):
    if measure == 'visitors':
        return vis.get((ym, axis, key, aud))
    b = buy.get((ym, axis, key, aud))
    if measure == 'orders':
        return b['orders'] if b else 0
    if measure == 'amount':
        return b['amount'] if b else 0
    if measure == 'conv':
        v = vis.get((ym, axis, key, aud))
        if not v:
            return None
        return (b['orders'] if b else 0) / float(v)
    return None


def _rows_for(buy, vis, days, calc_months, axis, keys, aud, measure, kind):
    out = []
    for key in keys:
        d = {}
        for ym in calc_months:
            d[ym] = _val(buy, vis, ym, axis, key, aud, measure)
        out.append(R.row(key, kind, d))
    # 합계 / 일평균 — 전환율은 합계를 다시 나눠야 합니다(평균의 평균이 아님).
    tot = {}
    for ym in calc_months:
        tot[ym] = _val(buy, vis, ym, 'total', '합계', aud, measure)
    t = R.row('합계', kind, tot)
    t['total'] = True
    out.append(t)
    if measure != 'conv':
        avg = {}
        for ym in calc_months:
            v, n = tot.get(ym), days.get(ym)
            avg[ym] = (v / float(n)) if (v is not None and n) else None
        out.append(R.row('일평균', R.KIND_KRW if kind == R.KIND_KRW else R.KIND_FLOAT, avg,
                         '합계 ÷ 영업일 수'))
    return out


def _product_rows(rows, calc_months, aud, measure):
    """당월 매출 상위 10개 + 그 외. 순위는 기준월로 뽑고 추이는 13개월입니다."""
    per = {}      # sku -> ym -> dict(amount, qty)
    for r in rows:
        if r.channel != CHANNEL:
            continue
        foreign = r.nation != '내국인'
        if aud == 'foreign' and not foreign:
            continue
        if aud == 'local' and foreign:
            continue
        d = per.setdefault(r.sku, {}).setdefault(r.ym(), dict(amount=0, qty=0))
        d['amount'] += r.amount
        d['qty'] += r.qty

    field = 'qty' if measure == 'orders' else 'amount'
    kind = R.KIND_INT if field == 'qty' else R.KIND_KRW
    ranked = sorted(per, key=lambda s: -per[s].get(M.BASE_MONTH, {}).get(field, 0))
    top, rest = ranked[:10], ranked[10:]

    out = []
    for i, sku in enumerate(top, 1):
        meta = M.SKU_BY_CODE[sku]
        d = dict((ym, per[sku].get(ym, {}).get(field, 0)) for ym in calc_months)
        r = R.row('%d. %s' % (i, meta['name']), kind, d,
                  '%s · 정상가 %s' % (meta['line'], '₩' + format(meta['price'], ',')))
        out.append(r)
    d = {}
    for ym in calc_months:
        d[ym] = sum(per[s].get(ym, {}).get(field, 0) for s in rest)
    out.append(R.row('그 외 %d개' % len(rest), kind, d))
    tot = {}
    for ym in calc_months:
        tot[ym] = sum(per[s].get(ym, {}).get(field, 0) for s in per)
    t = R.row('합계', kind, tot)
    t['total'] = True
    out.append(t)
    return out


def build(rows, customers):
    traffic = L.store_traffic(rows)
    buy, vis, days = _index(rows, traffic)
    months = M.WINDOW_13
    calc_months = M.month_range(M.shift_month(months[0], -12), months[-1])

    views = {}
    for meas in MEASURES:
        for aud in AUDIENCES:
            k = '%s|%s' % (meas['key'], aud['key'])
            views[k] = dict(
                weekday=_rows_for(buy, vis, days, calc_months, 'weekday',
                                  M.WEEKDAYS, aud['key'], meas['key'], meas['kind']),
                hour=_rows_for(buy, vis, days, calc_months, 'hour',
                               M.HOURS, aud['key'], meas['key'], meas['kind']),
                product=_product_rows(rows, calc_months, aud['key'], meas['key'])
                        if meas['key'] in ('amount', 'orders') else None,
            )

    # 총괄 — 측정 토글과 무관하게 모든 지표를 한 장에 놓습니다.
    summary = []
    for meas in MEASURES + [dict(key='aov', label='객단가', kind=R.KIND_KRW)]:
        for aud in AUDIENCES:
            d = {}
            for ym in calc_months:
                if meas['key'] == 'aov':
                    b = buy.get((ym, 'total', '합계', aud['key']))
                    d[ym] = (b['amount'] / float(b['orders'])) if (b and b['orders']) else None
                else:
                    d[ym] = _val(buy, vis, ym, 'total', '합계', aud['key'], meas['key'])
            r = R.row('%s · %s' % (meas['label'], aud['label']), meas['kind'], d)
            r['indent'] = 0 if aud['key'] == 'all' else 1
            if aud['key'] == 'all':
                r['total'] = True
            summary.append(r)

    # 국적별 — 외국인 안의 구분이라 대상 토글과 무관합니다.
    nation_rows = {}
    for meas in ('amount', 'orders'):
        kind = R.KIND_KRW if meas == 'amount' else R.KIND_INT
        rs = []
        for nat in M.NATIONS:
            d = {}
            for ym in calc_months:
                d[ym] = _val(buy, vis, ym, 'nation', nat, 'all', meas)
            r = R.row(nat, kind, d)
            r['indent'] = 1
            rs.append(r)
        d = {}
        for ym in calc_months:
            d[ym] = _val(buy, vis, ym, 'total', '합계', 'foreign', meas)
        r = R.row('외국인 합계', kind, d)
        r['total'] = True
        rs.insert(0, r)
        d = {}
        for ym in calc_months:
            d[ym] = _val(buy, vis, ym, 'nation', '내국인', 'all', meas)
        rs.append(R.row('내국인', kind, d))
        nation_rows[meas] = rs

    return dict(
        title='플래그십 리포트',
        base=M.month_key(M.BASE_MONTH),
        months=R.month_labels(),
        measures=MEASURES,
        audiences=AUDIENCES,
        summary=summary,
        views=views,
        nation=nation_rows,
        notes=[
            '방문객은 원장에 없습니다 — 들어왔지만 사지 않은 사람은 주문을 '
            '남기지 않습니다. 영업일 × 시간대 × 내/외국인 전 슬롯에 통행량을 '
            '만들고, 구매건수는 원장에서 그대로 가져옵니다. 두 값이 서로 다른 '
            '데서 오면 전환율이 거짓이 됩니다.',
            '구매전환율의 합계는 각 칸 전환율의 평균이 아니라 합계끼리 나눈 '
            '값입니다. 평균을 내면 방문객이 적은 시간대가 과대 반영됩니다.',
            '국적은 외국인 안의 구분이라 대상 토글과 무관합니다.',
            '상품 순위는 기준월 기준으로 뽑고, 추이는 그 상품들의 13개월을 '
            '따라갑니다 — 순위가 바뀌는 것도 함께 보입니다.',
        ],
    )


def check(payload):
    """전환율이 100%를 넘거나 대상 합이 안 맞으면 빌드를 세웁니다.

    방문객과 구매건수를 서로 다른 데서 가져오면 전환율이 조용히 100%를
    넘습니다. 표에서는 '전환이 아주 좋은 시간대' 처럼 보입니다.
    """
    for key, view in payload['views'].items():
        if not key.startswith('conv|'):
            continue
        for axis in ('weekday', 'hour'):
            for r in view[axis]:
                for i, v in enumerate(r['values']):
                    assert v is None or v <= 1.0, (
                        '%s / %s / %s: %d번째 달 전환율 %.1f%%'
                        % (key, axis, r['name'], i, v * 100))

    # 전체 = 외국인 + 내국인 (방문객·구매건수·매출)
    for meas in ('visitors', 'orders', 'amount'):
        for axis in ('weekday', 'hour'):
            a = payload['views']['%s|all' % meas][axis]
            f = payload['views']['%s|foreign' % meas][axis]
            l = payload['views']['%s|local' % meas][axis]
            for ri in range(len(a)):
                if a[ri]['name'] == '일평균':
                    continue
                for i in range(len(a[ri]['values'])):
                    av, fv, lv = a[ri]['values'][i], f[ri]['values'][i], l[ri]['values'][i]
                    if av is None:
                        continue
                    assert abs(av - ((fv or 0) + (lv or 0))) < 1e-6, (
                        '%s/%s/%s %d번째 달: 전체 %s ≠ 외국인 %s + 내국인 %s'
                        % (meas, axis, a[ri]['name'], i, av, fv, lv))
    return True


def main():
    rows, customers = L.build_calibrated()
    payload = build(rows, customers)
    check(payload)
    out = os.path.abspath(OUT)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    n = R.js_file(out, 'FLAGSHIP_DATA', payload, payload['title'])
    print('data/flagship.js  %s bytes  (조합 %d)' % (format(n, ','), len(payload['views'])))


if __name__ == '__main__':
    main()
