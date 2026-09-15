# -*- coding: utf-8 -*-
"""품목별 판매 현황 (원본 'Chart') — 원장 → data/items.js

원본은 월별 탭마다 **327행 × 245열** 짜리 표 하나입니다. 앞선 판(요약 KPI +
히트맵 + 13개월 추이)은 읽기는 편했지만 **원본과 다른 표**였습니다. 이번에는
그 표를 그대로 옮깁니다.

행 — 5단
    ALL → 카테고리 → 제품라인 → 변형(bottle/refill/set) → SKU
    세트는 원본이 SUMMARY 와 DETAILS 로 구획을 나눠 둡니다. 여러 라인을 묶은
    상품이라 '어느 라인의 매출인가' 가 하나로 안 정해지기 때문입니다. 같은
    이유로 여기서도 아래 별도 구획으로 내려 둡니다.

열 — 수량 블록 다음에 금액 블록, 각각 MTD / YTD
    수량 MTD  전년동월 · 당월(+채널별) · YoY · 전월(+채널별) · MoM
    수량 YTD  2025(ALL) · 2025(YoY) · 당해 누계(+채널별 +수출국가별) · YoY
    금액 MTD  전년동월 · 당월(+채널별) · YoY · 전월 · MoM
    금액 YTD  수량 YTD 와 같음
    값 옆에는 항상 `shr` 이 붙습니다.

원본과 다르게 한 곳은 둘뿐입니다.

1. **행 이름을 왼쪽에 고정**했습니다. 원본은 라벨이 155열, 즉 표 한가운데에
   있습니다 — 수량 블록을 왼쪽, 금액 블록을 오른쪽에 두고 그 사이에 이름을
   끼운 배치입니다. 종이에서는 되지만 가로 스크롤에서는 이름이 화면 밖으로
   나갑니다.
2. **계층을 들여쓰기로** 보입니다. 원본은 굵기로만 구분해 4단이 한 칸에
   겹쳐 있습니다.

금액 MTD 의 전월에 채널 분해가 없는 것은 원본 그대로입니다. 대칭으로
맞추고 싶은 자리지만, 옮겨 만든다는 약속이 먼저입니다.

`shr` 의 분모는 **그 기간 ALL 행의 값**입니다 — 자기 행의 합이 아닙니다.
HOME CARE 의 자사몰 수량 옆 0.09 는 '자사몰 안에서 9%' 가 아니라 '그 달
전체 수량의 9%' 라는 뜻입니다. 화면에서는 계산해서 그리므로 원장 값만
싣습니다.
"""

import os

import master as M
import ledger as L
import reportlib as R

OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'items.js')

TITLE = '품목별 판매 현황'

# 변형 그룹의 표기. 원본이 소문자 영문으로 적어 둔 그대로입니다.
VARIANT_LABEL = dict(bottle='bottle', refill='refill', set='set')
# 단품에도 'set' 변형이 있습니다(한 코드로 파는 기프트 구성). 여러 라인을
# 묶은 BUNDLES 와는 다른 것이라 SUMMARY 구획에 그대로 둡니다.
SHOW_VARIANTS = M.VARIANTS


def _index(rows):
    """[measure][sku][channel][ym] 과 [measure][sku][dest][ym]."""
    cell = dict(qty={}, val={})
    nat = dict(qty={}, val={})
    for r in rows:
        for key, v in (('qty', r.qty), ('val', r.amount)):
            d = cell[key].setdefault(r.sku, {}).setdefault(r.channel, {})
            ym = r.ym()
            d[ym] = d.get(ym, 0) + v
            if r.dest:
                d2 = nat[key].setdefault(r.sku, {}).setdefault(r.dest, {})
                d2[ym] = d2.get(ym, 0) + v
    return cell, nat


def _row_defs():
    """원본의 행 계층 그대로. skus 는 그 행이 합산할 SKU 코드들입니다."""
    defs = []

    def add(lv, name, skus, **kw):
        d = dict(lv=lv, name=name, skus=[s['sku'] for s in skus])
        d.update(kw)
        defs.append(d)
        return d

    add(0, 'ALL', M.SINGLES, total=True, sec='sum')
    for cat in M.CATEGORIES:
        cat_skus = [s for s in M.SINGLES if s['cat'] == cat]
        if not cat_skus:
            continue
        add(1, cat, cat_skus)
        for line in M.LINES:
            if line['cat'] != cat:
                continue
            line_skus = [s for s in cat_skus if s['line'] == line['code']]
            if not line_skus:
                continue
            add(2, '%s %s' % (line['code'], line['name']), line_skus,
                note=line['cat'])
            for vg in SHOW_VARIANTS:
                vsk = [s for s in line_skus if s['variant'] == vg]
                if not vsk:
                    continue
                add(3, VARIANT_LABEL[vg], vsk)
                for s in vsk:
                    add(4, s['name'], [s], code=s['sku'])

    # ── DETAILS — 세트 ───────────────────────────────────────────────
    add(0, '세트 합계', M.BUNDLES, total=True, sec='det')
    for line in M.LINES:
        bsk = [s for s in M.BUNDLES if s['line'] == line['code']]
        if not bsk:
            continue
        add(1, '%s %s' % (line['code'], line['name']), bsk, sec='det')
        for s in bsk:
            add(2, s['name'], [s], code=s['sku'], sec='det')
    return defs


def _sum(src, skus, chans, months):
    t = 0
    for sk in skus:
        per = src.get(sk)
        if not per:
            continue
        for ch in chans:
            d = per.get(ch)
            if not d:
                continue
            for ym in months:
                t += d.get(ym, 0)
    return t


def build(rows, customers):
    cell, nat = _index(rows)
    base = M.BASE_MONTH                       # (2026, 7)
    prev_year = (base[0] - 1, base[1])
    prev_month = M.shift_month(base, -1)

    ytd_cur = [(base[0], m) for m in range(1, base[1] + 1)]
    ytd_py = [(base[0] - 1, m) for m in range(1, base[1] + 1)]
    year_py = [(base[0] - 1, m) for m in range(1, 13)]

    defs = _row_defs()
    ch_keys = M.CHANNEL_KEYS
    nations = M.EXPORT_NATIONS

    grid = {}
    for meas in ('qty', 'val'):
        src = cell[meas]
        nsrc = nat[meas]

        def vec(months, chans=ch_keys):
            return [_sum(src, d['skus'], chans, months) for d in defs]

        def mat(months):
            return [[_sum(src, d['skus'], [ch], months) for ch in ch_keys]
                    for d in defs]

        mtd = dict(py=vec([prev_year]),
                   cur=vec([base]),
                   cur_ch=mat([base]),
                   pm=vec([prev_month]))
        # 금액 MTD 의 전월은 원본에 채널 분해가 없습니다.
        if meas == 'qty':
            mtd['pm_ch'] = mat([prev_month])

        nat_mat = []
        for d in defs:
            line_vals = []
            for nt in nations:
                t = 0
                for sk in d['skus']:
                    per = nsrc.get(sk)
                    if not per:
                        continue
                    dd = per.get(nt)
                    if not dd:
                        continue
                    for ym in ytd_cur:
                        t += dd.get(ym, 0)
                line_vals.append(t)
            nat_mat.append(line_vals)

        ytd = dict(y_all=vec(year_py),
                   y_ytd=vec(ytd_py),
                   cur=vec(ytd_cur),
                   cur_ch=mat(ytd_cur),
                   cur_nat=nat_mat)

        grid[meas + '|mtd'] = mtd
        grid[meas + '|ytd'] = ytd

    out_rows = [dict(lv=d['lv'], name=d['name'], sec=d.get('sec', 'sum'),
                     code=d.get('code'), note=d.get('note'),
                     total=bool(d.get('total')))
                for d in defs]

    return dict(
        title=TITLE,
        base=M.month_key(base),
        cols=dict(py=M.month_key(prev_year), cur=M.month_key(base),
                  pm=M.month_key(prev_month),
                  y_all='%d(ALL)' % (base[0] - 1),
                  y_ytd='%d(YoY)' % (base[0] - 1)),
        channels=[dict(key=c['key'], group=c['group'], sub=c['sub'],
                       model=c['model'], inactive=(c['status'] == 'INACTIVE'))
                  for c in M.CHANNELS],
        nations=nations,
        rows=out_rows,
        grid=grid,
        notes=[
            '원본 시트의 표를 그대로 옮긴 화면입니다 — 행 5단(ALL → 카테고리 → '
            '제품라인 → 변형 → SKU), 열은 수량·금액 각각 MTD / YTD 입니다.',
            '`shr` 의 분모는 **그 기간 ALL 행의 값**입니다. 자기 행의 합이 '
            '아닙니다 — 어느 칸이든 그 달 전체에서 차지하는 몫으로 읽습니다.',
            '**세트는 아래 별도 구획**입니다. 여러 라인을 묶은 상품이라 어느 '
            '라인의 매출인지 하나로 정해지지 않습니다 — 위 SUMMARY 구획의 '
            'ALL 에는 들어가지 않습니다.',
            '금액 MTD 의 전월에는 채널 분해가 없습니다 — 원본 그대로입니다.',
            '행 이름은 원본에서 표 한가운데(155열)에 있습니다. 가로 스크롤에서 '
            '이름이 화면 밖으로 나가므로 **왼쪽에 고정**했습니다.',
            'MTD 는 기준월 한 달, YTD 는 그 해 1월부터 기준월까지의 누계입니다. '
            '2025(ALL) 은 전년 12개월 전체, 2025(YoY) 는 전년 같은 기간입니다.',
            '금액은 sell-out(소비자 판매가) 기준입니다. 판매처별 리포트의 '
            'sell-in 과 섞지 마세요.',
        ],
    )


def check(payload):
    """계층 합계와 구획 분리를 봅니다.

    소계를 따로 더하면 하위 합과 어긋나기 쉽고, 표에서는 '반올림 차이' 처럼
    보여 눈으로는 안 걸립니다.
    """
    rows = payload['rows']
    grid = payload['grid']
    n = len(rows)

    def block_vectors(block):
        out = []
        for k, v in block.items():
            if not v:
                continue
            if isinstance(v[0], list):
                for ci in range(len(v[0])):
                    out.append((k + '[%d]' % ci, [r[ci] for r in v]))
            else:
                out.append((k, v))
        return out

    # 1. 계층 합계 = 하위 합. 구획(sum/det)마다 따로 봅니다.
    for gk, block in grid.items():
        for vk, col in block_vectors(block):
            for sec in ('sum', 'det'):
                idxs = [i for i in range(n) if rows[i]['sec'] == sec]
                if not idxs:
                    continue
                stack = []            # (lv, index, 누적합, 자식있음)
                def close(upto):
                    while stack and stack[-1][0] >= upto:
                        plv, pi, acc, kids = stack.pop()
                        # 잎(SKU)은 하위가 없으니 검산 대상이 아닙니다
                        assert not kids or acc == col[pi], (
                            '%s/%s: %s 행 합계 %s 과 하위 합 %s 이 다릅니다'
                            % (gk, vk, rows[pi]['name'],
                               format(col[pi], ','), format(acc, ',')))
                        if stack:
                            stack[-1] = (stack[-1][0], stack[-1][1],
                                         stack[-1][2] + col[pi], True)
                for i in idxs:
                    close(rows[i]['lv'])
                    stack.append((rows[i]['lv'], i, 0, False))
                close(-1)

    # 2. 채널 분해의 합 = 그 기간의 총액. 분해가 총액과 다른 데서 오면
    #    화면의 shr 이 100% 를 넘거나 모자랍니다.
    pairs = [('cur_ch', 'cur'), ('pm_ch', 'pm')]
    for gk, block in grid.items():
        for mk, tk in pairs:
            if mk not in block:
                continue
            for i in range(n):
                s = sum(block[mk][i])
                assert s == block[tk][i], (
                    '%s: %s 행에서 채널 합 %s 과 %s 총액 %s 이 다릅니다'
                    % (gk, rows[i]['name'], format(s, ','), tk,
                       format(block[tk][i], ',')))

    # 3. 수출 국가별 합 = 수출 채널의 YTD 값
    ci = [c['key'] for c in payload['channels']].index('수출')
    for meas in ('qty', 'val'):
        b = grid[meas + '|ytd']
        for i in range(n):
            s = sum(b['cur_nat'][i])
            assert s == b['cur_ch'][i][ci], (
                '%s: %s 행에서 수출 국가 합 %s 과 수출 채널 %s 이 다릅니다'
                % (meas, rows[i]['name'], format(s, ','),
                   format(b['cur_ch'][i][ci], ',')))

    # 4. 두 구획이 겹치지 않는지. 세트가 SUMMARY 의 ALL 에 섞여 들어가면
    #    라인별 합이 맞는 채로 총합만 부풀어 눈에 안 띕니다.
    codes = {}
    for r in rows:
        if r['code']:
            assert r['code'] not in codes, 'SKU %s 가 두 번 나옵니다' % r['code']
            codes[r['code']] = r['sec']
    for s in M.BUNDLES:
        assert codes.get(s['sku']) == 'det', \
            '세트 %s 가 SUMMARY 구획에 있습니다' % s['sku']
    for s in M.SINGLES:
        assert codes.get(s['sku']) == 'sum', \
            '단품 %s 가 SUMMARY 구획에 없습니다' % s['sku']

    # 5. YTD 누계 ≥ MTD. 누계가 당월보다 작으면 기간을 잘못 짚은 것입니다.
    for meas in ('qty', 'val'):
        a = grid[meas + '|mtd']['cur'][0]
        b = grid[meas + '|ytd']['cur'][0]
        assert b >= a, '%s: YTD(%s) 가 MTD(%s) 보다 작습니다' % (meas, b, a)
    return True


def main():
    rows, customers = L.build_calibrated()
    payload = build(rows, customers)
    check(payload)
    out = os.path.abspath(OUT)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    n = R.js_file(out, 'ITEMS_DATA', payload, payload['title'])
    print('data/items.js  %s bytes  (행 %d · 채널 %d)'
          % (format(n, ','), len(payload['rows']), len(payload['channels'])))


if __name__ == '__main__':
    main()
