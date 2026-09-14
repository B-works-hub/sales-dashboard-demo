# -*- coding: utf-8 -*-
"""판매처별 리포트 — 원장 → data/channel.js

이 리포트에는 장부가 두 개 있습니다.

  sell-out   소비자가 산 금액. 원장 그대로입니다.
  sell-in    우리 장부에 잡히는 금액. 소비자가에서 결제수수료·판매수수료·
             도매마진이 빠진 공급가입니다.

같은 7월인데 두 값이 다르고, 채널 순위도 바뀝니다. 위탁 채널은 공급가율이
낮아 sell-out 에서 크게 보이던 곳이 sell-in 에서는 내려앉습니다.

**한 화면에서 두 장부를 섞지 않습니다.** 일일 대시보드의 마감/잠정 배지와
같은 원칙입니다 — 섞으면 비중의 분모와 분자가 서로 다른 장부에서 와서,
합이 100%가 되는데도 틀린 표가 나옵니다.

직매입 채널은 한 가지가 더 있습니다. 채널이 물건을 미리 사가므로 발주가
덩어리로 들어오고, **월별로는 두 장부가 어긋났다가 연 누적에서 수렴합니다.**
이걸 평평하게 만들면 이중 장부를 둘 이유 자체가 사라집니다.
"""

import os
import random

import master as M
import ledger as L
import reportlib as R

OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'channel.js')
SEED = 20260901

LEDGERS = [
    dict(key='sellout', label='sell-out', badge='소비자 판매가',
         note='소비자가 실제로 지불한 금액입니다. 채널 수수료가 빠지기 전입니다.'),
    dict(key='sellin', label='sell-in', badge='공급가',
         note='우리 장부에 잡히는 금액입니다. 소비자가에서 결제수수료·판매'
              '수수료·도매마진이 빠집니다. 직매입 채널은 발주가 덩어리로 '
              '들어와 월별로 어긋나고, 연 누적에서 sell-out × 공급가율로 '
              '수렴합니다.'),
]


def _sellout(rows):
    out = {}
    for r in rows:
        out.setdefault(r.channel, {})
        out[r.channel][r.ym()] = out[r.channel].get(r.ym(), 0) + r.amount
    return out


def _sellin(sellout):
    """sell-out → sell-in.

    직영·위탁은 팔린 달에 그대로 정산되므로 공급가율만 곱합니다.
    직매입은 채널이 미리 사가므로 달마다 ±35% 로 흔들립니다.

    흔들린 값을 그대로 두면 두 장부의 비율이 아무 데로나 흘러가므로 다시
    정규화해야 하는데, **어느 창에서 맞출지가 중요합니다.** 달마다 그 달
    기준 직전 12개월로 맞추면 한 달이 12개 창에 속해 서로 충돌하고, 결국
    어느 창에서도 정확히 맞지 않습니다(공급가율에서 최대 5%p 어긋났습니다).
    리포트가 실제로 보여주는 창(직전 13개월)에서 한 번 맞춥니다 — 그래야
    화면의 장부 대조표가 정확히 공급가율을 가리킵니다.
    """
    out = {}
    for ch in M.CHANNELS:
        ratio = ch['sellin']
        so = sellout.get(ch['key'], {})
        si = {}
        if ch['model'] != '직매입':
            for ym, v in so.items():
                si[ym] = int(round(v * ratio))
        else:
            raw = {}
            for ym, v in so.items():
                rng = random.Random('%s|%s|%d-%02d' % (SEED, ch['key'], ym[0], ym[1]))
                raw[ym] = v * ratio * rng.uniform(0.65, 1.35)
            num = sum(so.get(w, 0) for w in M.WINDOW_13) * ratio
            den = sum(raw.get(w, 0) for w in M.WINDOW_13)
            scale = (num / den) if den else 1.0
            for ym, v in raw.items():
                si[ym] = int(round(v * scale))
        out[ch['key']] = si
    return out


def _hier_rows(amount, months, calc_months, as_mix=False):
    """계층 합계 + 채널. 원본의 '카테고리별 shr' 구조를 그대로 옮깁니다."""
    def total(keys):
        d = {}
        for ym in calc_months:
            d[ym] = sum(amount.get(k, {}).get(ym, 0) for k in keys)
        return d

    all_keys = M.CHANNEL_KEYS
    grand = total(all_keys)

    def mk(name, keys, indent, note=None):
        vals = total(keys)
        if as_mix:
            r = R.ratio_row(name, vals, grand, note=note, min_den=1)
        else:
            r = R.row(name, R.KIND_KRW, vals, note=note)
        r['indent'] = indent
        return r

    rows = [mk('전체', all_keys, 0)]
    rows[0]['total'] = True

    for group in ('온라인', '오프라인', '글로벌'):
        gkeys = [c['key'] for c in M.CHANNELS if c['group'] == group]
        if not gkeys:
            continue
        rows.append(mk(group, gkeys, 1))
        subs = []
        for c in M.CHANNELS:
            if c['group'] == group and c['sub'] not in subs:
                subs.append(c['sub'])
        for sub in subs:
            skeys = [c['key'] for c in M.CHANNELS
                     if c['group'] == group and c['sub'] == sub]
            rows.append(mk(sub, skeys, 2))
            for c in M.CHANNELS:
                if c['group'] != group or c['sub'] != sub:
                    continue
                note = '%s · %s 입점' % (c['model'], c['opened'])
                if c['closed']:
                    note += ' · %s 거래종료' % c['closed']
                note += ' · 공급가율 %.0f%%' % (c['sellin'] * 100)
                r = mk(c['key'], [c['key']], 3, note)
                if c['status'] == 'INACTIVE':
                    r['inactive'] = True
                rows.append(r)
    return rows


def _rank_rows(amount, months, calc_months, top=10):
    """당월 상위 10곳 + 그 외. 계층을 접고 크기 순으로만 봅니다."""
    cur = M.BASE_MONTH
    size = sorted(((sum(amount.get(c['key'], {}).get(cur, 0) for _ in [0]), c['key'])
                   for c in M.CHANNELS), reverse=True)
    ranked = [k for _, k in size[:top]]
    rest = [c['key'] for c in M.CHANNELS if c['key'] not in ranked]

    grand = {}
    for ym in calc_months:
        grand[ym] = sum(amount.get(k, {}).get(ym, 0) for k in M.CHANNEL_KEYS)

    rows = []
    for i, k in enumerate(ranked, 1):
        d = dict((ym, amount.get(k, {}).get(ym, 0)) for ym in calc_months)
        r = R.ratio_row('%d. %s' % (i, k), d, grand, min_den=1)
        rows.append(r)
    d = {}
    for ym in calc_months:
        d[ym] = sum(amount.get(k, {}).get(ym, 0) for k in rest)
    rows.append(R.ratio_row('그 외 %d곳' % len(rest), d, grand, min_den=1))
    return rows


def build(rows, customers):
    months = M.WINDOW_13
    calc_months = M.month_range(M.shift_month(months[0], -12), months[-1])
    sellout = _sellout(rows)
    sellin  = _sellin(sellout)
    books = dict(sellout=sellout, sellin=sellin)

    ledgers = {}
    for spec in LEDGERS:
        amt = books[spec['key']]
        ledgers[spec['key']] = dict(
            label=spec['label'], badge=spec['badge'], note=spec['note'],
            sections=[
                dict(key='amount', label='채널별 매출',
                     rows=_hier_rows(amt, months, calc_months, as_mix=False)),
                dict(key='mix', label='채널별 비중',
                     rows=_hier_rows(amt, months, calc_months, as_mix=True)),
                dict(key='rank', label='당월 순위 TOP 10',
                     rows=_rank_rows(amt, months, calc_months)),
            ],
        )

    # 두 장부 대조 — 비율이 공급가율 근처에 있어야 정상입니다.
    rec = []
    grand_o, grand_i = {}, {}
    for ym in calc_months:
        grand_o[ym] = sum(sellout.get(k, {}).get(ym, 0) for k in M.CHANNEL_KEYS)
        grand_i[ym] = sum(sellin.get(k, {}).get(ym, 0) for k in M.CHANNEL_KEYS)
    r = R.ratio_row('전체', grand_i, grand_o, min_den=1,
                    note='sell-in ÷ sell-out')
    r['indent'] = 0
    r['total'] = True
    rec.append(r)
    for c in M.CHANNELS:
        if c['status'] == 'INACTIVE':
            continue
        r = R.ratio_row(c['key'], sellin.get(c['key'], {}),
                        sellout.get(c['key'], {}), min_den=1,
                        note='%s · 공급가율 기준 %.0f%%' % (c['model'], c['sellin'] * 100))
        r['indent'] = 1
        r['target'] = c['sellin']
        rec.append(r)

    return dict(
        title='판매처별 리포트',
        base=M.month_key(M.BASE_MONTH),
        months=R.month_labels(),
        ledgers=ledgers,
        ledger_order=[s['key'] for s in LEDGERS],
        reconcile=dict(key='reconcile', label='장부 대조 (sell-in ÷ sell-out)', rows=rec),
        notes=[
            '한 화면에서 두 장부를 섞지 않습니다. 비중의 분자와 분모가 서로 '
            '다른 장부에서 오면 합은 100%가 되는데도 틀린 표가 됩니다.',
            'sell-out 은 소비자가, sell-in 은 공급가입니다. 채널 수수료와 '
            '도매마진만큼 차이가 납니다 — 직영몰도 결제수수료·부가세가 빠져 '
            '1:1 이 아닙니다.',
            '직매입 채널은 발주가 덩어리로 들어와 월별로 두 장부가 어긋납니다. '
            '직전 13개월 누적에서 공급가율로 수렴합니다.',
            '장부 대조에서 직매입 채널은 100%를 넘는 달이 나옵니다 — 그 달 '
            '팔린 것보다 많이 발주해 채널 재고가 늘었다는 뜻이고, 오류가 '
            '아닙니다. 직영·위탁은 팔린 달에 정산되므로 늘 고정 비율입니다.',
            '전 채널을 봅니다 — 고객·상품별 리포트(식별 가능 채널)와 분모가 다릅니다.',
        ],
    )


def check(payload):
    """장부 대조가 공급가율에서 크게 벗어나면 빌드를 세웁니다.

    sell-in 을 만드는 과정에서 정규화를 빼먹으면 비율이 조용히 흘러갑니다.
    표에서는 그냥 '수수료가 좀 다른 채널' 처럼 보여 눈으로는 안 걸립니다.
    """
    bad = []
    for r in payload['reconcile']['rows']:
        if 'target' not in r or r['avg'] is None:
            continue
        if abs(r['avg'] - r['target']) > 0.03:
            bad.append('%s: 실측 %.3f vs 기준 %.3f' % (r['name'], r['avg'], r['target']))
    assert not bad, '장부 대조가 공급가율과 어긋납니다:\n  ' + '\n  '.join(bad)

    # 비중은 각 장부 안에서 100% 가 되어야 합니다.
    for key, led in payload['ledgers'].items():
        mix = [s for s in led['sections'] if s['key'] == 'mix'][0]
        top = [r for r in mix['rows'] if r.get('total')][0]
        for i, v in enumerate(top['values']):
            if v is None:
                continue
            assert abs(v - 1.0) < 1e-6, '%s 비중 합계가 %d번째 달에 %.4f' % (key, i, v)
    return True


def main():
    rows, customers = L.build_calibrated()
    payload = build(rows, customers)
    check(payload)
    out = os.path.abspath(OUT)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    n = R.js_file(out, 'CHANNEL_DATA', payload, payload['title'])
    print('data/channel.js  %s bytes  (장부 %d · 채널 %d)'
          % (format(n, ','), len(payload['ledgers']), len(M.CHANNELS)))


if __name__ == '__main__':
    main()
