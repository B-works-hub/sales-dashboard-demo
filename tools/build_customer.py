# -*- coding: utf-8 -*-
"""고객 리포트 — 원장 → data/customer.js

원본 리포트의 지표 정의를 그대로 옮깁니다. 정의가 화면에 적혀 있지 않으면
숫자가 이상할 때 어디부터 봐야 할지 알 수 없습니다. 그래서 지표마다 note 를
달고, 화면 각주로 내립니다.

모든 지표는 **자사몰 · 구매자 키 기준**입니다. 원본이 '주문자 휴대전화번호
기준'이라고 적어 둔 자리이고, 한 사람이 여러 번 사도 한 명입니다.
"""

import os
import statistics

import master as M
import ledger as L
import reportlib as R

CHANNEL = '자사몰'
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'customer.js')

# 직전 12개월 판정에 쓸 여유 구간 — 13개월 창보다 12개월 더 앞을 봅니다.
LOOKBACK = 12


def _index(rows):
    """자사몰 주문을 월 → 고객 으로 접습니다."""
    by_month = {}          # ym -> {cust: dict(rev, orders, gift, member)}
    for r in rows:
        if r.channel != CHANNEL:
            continue
        ym = r.ym()
        m = by_month.setdefault(ym, {})
        c = m.setdefault(r.cust, dict(rev=0, orders=set(), gift=False,
                                      member=r.member, age=r.age, subs=r.subs,
                                      dates=set()))
        c['rev'] += r.amount
        c['orders'].add(r.order)
        c['dates'].add(r.date)
        if r.gift:
            c['gift'] = True
    return by_month


def _window(by_month, ym, back=LOOKBACK):
    """ym 직전 back 개월(당월 제외)에 산 고객 집합."""
    out = set()
    for k in range(1, back + 1):
        out |= set(by_month.get(M.shift_month(ym, -k), {}))
    return out


def build(rows, customers):
    build._gone_prev = set()      # 이탈 판정은 전월 상태와 비교합니다
    by_month = _index(rows)
    cust_by_key = dict((c.key, c) for c in customers)
    months = M.WINDOW_13
    # 전년동월 비교를 위해 13개월 창보다 12개월 앞까지 계산해 둡니다.
    calc_months = M.month_range(M.shift_month(months[0], -12), months[-1])

    visits    = L.traffic(rows)
    acc = dict((k, {}) for k in (
        'visit', 'signup', 'active', 'retained',
        'buy', 'buy_m', 'buy_n', 'buy_n_first', 'first', 'repeat',
        'cycle', 'rep_avg', 'rep_med', 'rep_max',
        'aov', 'rev', 'gift', 'churn', 'churn_rate', 'churn_cum', 'winback',
    ))
    ages = dict((a, {}) for a in M.AGE_BANDS)
    subs = dict((k, {}) for k in ('subs_active', 'subs_buy', 'subs_rev', 'mall_rev'))

    ever_before = set()     # 그 달 이전에 한 번이라도 산 고객

    for ym in calc_months:
        cur = by_month.get(ym, {})
        prev12 = _window(by_month, ym)

        buyers   = set(cur)
        members  = set(k for k, v in cur.items() if v['member'])
        nonmem   = buyers - members
        firsts   = buyers - prev12 - ever_before
        repeats  = buyers & prev12

        acc['visit'][ym]  = visits[ym]['visits']
        acc['signup'][ym] = visits[ym]['signup']
        acc['active'][ym] = len(prev12 | buyers)
        acc['retained'][ym] = len([c for c in customers if c.member and c.joined <= ym])

        acc['buy'][ym]   = len(buyers)
        acc['buy_m'][ym] = len(members)
        acc['buy_n'][ym] = len(nonmem)
        acc['buy_n_first'][ym] = len(nonmem & firsts)
        acc['first'][ym]  = len(firsts)
        acc['repeat'][ym] = len(repeats)

        # 재구매 주기·횟수 — 12개월 내 2회 이상 산 고객만
        counts, cycles = [], []
        for c in repeats:
            dates = set()
            for k in range(0, LOOKBACK + 1):
                dates |= by_month.get(M.shift_month(ym, -k), {}).get(c, {}).get('dates', set())
            dates = sorted(dates)
            if len(dates) < 2:
                continue
            counts.append(len(dates))
            gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
            cycles.append(sum(gaps) / float(len(gaps)))
        acc['cycle'][ym]   = (sum(cycles) / len(cycles)) if cycles else None
        acc['rep_avg'][ym] = (sum(counts) / float(len(counts))) if counts else None
        acc['rep_med'][ym] = statistics.median(counts) if counts else None
        acc['rep_max'][ym] = max(counts) if counts else None

        rev = sum(v['rev'] for v in cur.values())
        acc['rev'][ym] = rev
        acc['aov'][ym] = int(rev / len(buyers)) if buyers else None
        acc['gift'][ym] = len([k for k, v in cur.items() if v['gift']])

        # 이탈 — '최근 12개월 무구매' 상태로 **이번 달에 넘어온** 고객입니다.
        #
        # 원본 시트의 각주는 '런칭 이후 구매 이력이 있는 고객 중 최근 12개월
        # 무구매'라고 누적으로 적혀 있지만, 적힌 값(월 수백 명)은 누적일 수
        # 없는 크기입니다. 각주와 숫자가 어긋나 있어, 숫자가 말이 되는 쪽으로
        # 계산하고 각주를 거기에 맞췄습니다. 누적 이탈은 따로 둡니다.
        gone_now  = set(k for k in ever_before if k not in prev12 and k not in buyers)
        gone_prev = getattr(build, '_gone_prev', set())
        newly_gone = gone_now - gone_prev
        build._gone_prev = gone_now

        acc['churn'][ym] = len(newly_gone)
        acc['churn_rate'][ym] = (len(newly_gone) / float(acc['active'][ym])
                                 if acc['active'][ym] else None)
        acc['churn_cum'][ym] = len(gone_now)
        acc['winback'][ym] = len(buyers & gone_prev)

        for a in M.AGE_BANDS:
            ages[a][ym] = len([k for k, v in cur.items() if v['age'] == a])

        s_buy = set(k for k, v in cur.items() if v['subs'])
        subs['subs_buy'][ym]    = len(s_buy)
        subs['subs_rev'][ym]    = sum(v['rev'] for k, v in cur.items() if v['subs'])
        subs['mall_rev'][ym]    = rev
        subs['subs_active'][ym] = len([c for c in customers
                                       if c.subs and c.joined <= ym]) // 6

        ever_before |= buyers

    K = R
    rows_main = [
        R.row('방문 수', K.KIND_INT, acc['visit'],
              '자사몰 방문 수 — 새로운 세션의 개수(세션 유지 2시간)'),
        R.row('신규 회원', K.KIND_INT, acc['signup'],
              '해당 월에 가입한 회원 수'),
        R.row('활성 고객(회원+비회원)', K.KIND_INT, acc['active'],
              '12개월 내 자사몰에서 구매이력 있는 고객 수 (구매자 키 기준)'),
        R.row('유지 고객(회원)', K.KIND_INT, acc['retained'],
              '휴면/탈퇴 없이 가입되어 있는 상태의 회원 수'),
        R.ratio_row('구매 고객(회원+비회원) 비중', acc['buy'], acc['active'],
                    '활성 고객 중 당월 구매 고객의 비중'),
        R.row('구매 고객(회원+비회원)', K.KIND_INT, acc['buy'],
              '당월 구매이력이 있는 고객 수 (구매자 키 기준)'),
        R.ratio_row('구매 고객(회원) 비중', acc['buy_m'], acc['buy'], None),
        R.row('구매 고객(회원)', K.KIND_INT, acc['buy_m'],
              '구매 고객 중 회원'),
        R.ratio_row('구매 고객(비회원) 비중', acc['buy_n'], acc['buy'], None),
        R.row('구매 고객(비회원)', K.KIND_INT, acc['buy_n'],
              '구매 고객 중 비회원'),
        R.ratio_row('구매 고객(비회원&&첫구매) 비중', acc['buy_n_first'], acc['buy'], None),
        R.row('구매 고객(비회원&&첫구매)', K.KIND_INT, acc['buy_n_first'],
              '구매 고객 중 비회원이면서 첫구매'),
        R.ratio_row('첫구매 고객(회원+비회원) 비중', acc['first'], acc['buy'], None),
        R.row('첫구매 고객(회원+비회원)', K.KIND_INT, acc['first'],
              '직전 12개월 내 구매이력이 없고 당월 첫구매한 고객'),
        R.ratio_row('재구매 고객(회원+비회원) 비중', acc['repeat'], acc['buy'], None),
        R.row('재구매 고객(회원+비회원)', K.KIND_INT, acc['repeat'],
              '당월 구매 고객 중 최근 12개월 내 구매이력이 당월 포함 2회 이상'),
        R.row('재구매 주기', K.KIND_DAYS, acc['cycle'],
              '12개월 내 2회 이상 구매한 고객의 구매 간격 평균(일)'),
        R.row('재구매 횟수(avg)', K.KIND_FLOAT, acc['rep_avg'], None),
        R.row('재구매 횟수(median)', K.KIND_FLOAT, acc['rep_med'], None),
        R.row('최대 재구매 횟수', K.KIND_INT, acc['rep_max'], None),
        R.row('객단가', K.KIND_KRW, acc['aov'],
              '당월 자사몰 매출 ÷ 당월 구매 고객 수'),
        R.ratio_row('선물구매 비중', acc['gift'], acc['buy'], None),
        R.row('선물구매', K.KIND_INT, acc['gift'],
              '당월 구매 고객 중 기프트 세트를 구매한 고객'),
        R.row('이탈률', K.KIND_PCT, acc['churn_rate'],
              '당월 이탈 고객 수 ÷ 활성 고객 수'),
        R.row('이탈고객수', K.KIND_INT, acc['churn'],
              "'최근 12개월 무구매' 상태로 당월에 넘어온 고객 — 누적이 아닙니다"),
        R.row('누적 이탈고객수', K.KIND_INT, acc['churn_cum'],
              '구매이력이 있으나 최근 12개월 내 구매가 없는 고객의 누계'),
        R.row('이탈 후 재구매', K.KIND_INT, acc['winback'],
              '이탈 상태였다가 당월 다시 구매한 고객'),
    ]

    rows_member = [
        R.row('회원 구매 고객 수', K.KIND_INT, acc['buy_m']),
        R.ratio_row('(비중)', acc['buy_m'], acc['buy']),
        R.row('비회원 구매 고객 수', K.KIND_INT, acc['buy_n']),
        R.ratio_row('(비중)', acc['buy_n'], acc['buy']),
        R.row('총 구매 고객 수', K.KIND_INT, acc['buy']),
    ]

    rows_age = []
    for a in M.AGE_BANDS:
        rows_age.append(R.row(a, K.KIND_INT, ages[a]))
        rows_age.append(R.ratio_row('(비중)', ages[a], acc['buy']))
    rows_age.append(R.row('총합계', K.KIND_INT, acc['buy']))

    rows_subs = [
        R.row('정기배송 활성 고객 수', K.KIND_INT, subs['subs_active'],
              '전월 유지 + 신규 − 이탈'),
        R.row('자사몰 활성 고객 수', K.KIND_INT, acc['active'],
              '최근 1년 내 구매이력 있는 고객'),
        R.ratio_row('정기배송 이용고객 비율', subs['subs_active'], acc['active']),
        R.row('정기배송 구매고객 수', K.KIND_INT, subs['subs_buy'],
              '당월 정기배송을 실제로 받은 고객'),
        R.row('자사몰 구매고객 수', K.KIND_INT, acc['buy'], '회원 + 비회원'),
        R.ratio_row('정기배송 구매고객 비율', subs['subs_buy'], acc['buy']),
        R.row('정기배송 매출', K.KIND_KRW, subs['subs_rev']),
        R.row('자사몰 매출', K.KIND_KRW, subs['mall_rev']),
        R.ratio_row('매출 비중', subs['subs_rev'], subs['mall_rev']),
    ]

    return dict(
        title='고객 리포트',
        base=M.month_key(M.BASE_MONTH),
        channel=CHANNEL,
        months=R.month_labels(),
        sections=[
            dict(key='kpi',    label='고객 지표',                    rows=rows_main),
            dict(key='member', label='회원 / 비회원 구매 수 추이',    rows=rows_member),
            dict(key='age',    label='고객 Profile — 연령대별',       rows=rows_age),
            dict(key='subs',   label='정기배송 이용 현황',            rows=rows_subs),
        ],
        notes=[
            '구매자 키 기준입니다 — 한 사람이 기간 안에 여러 번 사도 한 명입니다.',
            '비중 지표의 증감은 %p 로, 금액·수량 지표의 증감은 % 로 냅니다.',
            '월평균은 값이 있는 달만 나눕니다. 0 은 실적이므로 분모에 넣고, 빈 달은 뺍니다.',
        ],
    )


def main():
    rows, customers = L.build_calibrated()
    payload = build(rows, customers)
    out = os.path.abspath(OUT)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    n = R.js_file(out, 'CUSTOMER_DATA', payload, '고객 리포트')
    print('data/customer.js  %s bytes  (섹션 %d · 줄 %d)' % (
        format(n, ','), len(payload['sections']),
        sum(len(s['rows']) for s in payload['sections'])))


if __name__ == '__main__':
    main()
