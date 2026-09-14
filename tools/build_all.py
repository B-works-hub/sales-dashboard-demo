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
    # 앞으로: channel / chart / flagship
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
    for key, mod in BUILDERS:
        m = __import__(mod)
        payload = m.build(rows, customers)
        out = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                           'data', key + '.js'))
        varname = key.upper() + '_DATA'
        n = R.js_file(out, varname, payload, payload['title'])
        print('  data/%s.js  %s bytes' % (key, format(n, ',')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
