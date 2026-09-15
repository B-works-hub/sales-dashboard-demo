# -*- coding: utf-8 -*-
"""월간 리포트 데이터를 한 번에 만듭니다.

원장을 한 번만 만들어 모든 build_* 에 넘깁니다. 리포트마다 원장을 다시
생성하면 같은 시드를 써도 보정 반복 횟수가 달라져 값이 어긋날 수 있습니다.
"""

import sys

import master as M
import ledger as L
import reportlib as R

BUILDERS = [
    ('customer', 'build_customer'),
    ('product',  'build_product'),
    ('channel',  'build_channel'),
    ('items',    'build_items'),
    ('flagship', 'build_flagship'),
]


def main():
    print('마스터 자체검증 :', M.selftest())
    print('공통 집계 자체검증 :', R.selftest())
    print('원장 생성 …')
    rows, customers = L.build_calibrated(verbose=True)
    print('  주문 %s · 라인 %s · 고객 %s'
          % (format(len(set(r.order for r in rows)), ','),
             format(len(rows), ','),
             format(len(set(r.cust for r in rows)), ',')))

    import os
    built = {}
    for key, mod in BUILDERS:
        m = __import__(mod)
        payload = m.build(rows, customers)
        if hasattr(m, 'check'):
            m.check(payload)      # 조용히 틀린 값은 빌드를 세웁니다
        built[key] = payload
        out = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                           'data', key + '.js'))
        varname = key.upper() + '_DATA'
        n = R.js_file(out, varname, payload, payload['title'])
        print('  data/%s.js  %s bytes' % (key, format(n, ',')))

    cross_check(built)
    print('리포트 간 대조 : ok')
    return 0


def cross_check(built):
    """두 리포트가 같은 달에 대해 같은 금액을 말하는지 봅니다.

    '원장 하나에서 전부 집계한다' 는 이 저장소의 약속 자체입니다. 집계
    경로가 서로 다르므로(품목별은 SKU 축, 판매처별은 채널 축) 한쪽만
    고치면 조용히 어긋납니다 — 화면에서는 두 탭을 나란히 놓기 전까지
    아무도 모릅니다.

    품목별의 ALL 은 단품만입니다. 세트는 아래 구획으로 내려가 있으므로
    둘을 더해야 전체가 됩니다.
    """
    I, C = built['items'], built['channel']
    idx = dict((r['name'], i) for i, r in enumerate(I['rows']))
    total = (I['grid']['val|mtd']['cur'][0] +
             I['grid']['val|mtd']['cur'][idx['세트 합계']])
    row = [r for r in C['ledgers']['sellout']['sections'][0]['rows']
           if r['name'] == '전체'][0]
    assert total == row['values'][-1], (
        '품목별 %s 과 판매처별 sell-out %s 이 다릅니다 — 원장이 하나가 아닙니다'
        % (format(total, ','), format(row['values'][-1], ',')))


if __name__ == '__main__':
    sys.exit(main())
