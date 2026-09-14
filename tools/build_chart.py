# -*- coding: utf-8 -*-
"""Chart 리포트 — 원장 → data/chart.js

축이 네 개인 리포트입니다.

    제품라인(카테고리 계층)  ×  채널  ×  수량|금액  ×  당월|누적(YTD)

원본은 월별 탭마다 245열짜리 표를 깔아 두었습니다. 그대로 옮기면 화면에서
읽을 수가 없으므로, 교차는 한 시점의 히트맵으로 접고 추이는 13개월
매트릭스로 폅니다. 숫자는 같고 보는 방향만 둘로 나눈 것입니다.

MTD 는 기준월 한 달, YTD 는 그 해 1월부터 기준월까지의 누계입니다.
YTD 는 해가 바뀌면 리셋되므로 13개월 추이에서 1월에 뚝 떨어집니다 —
누계선의 정상 동작이고, 화면 각주에 적습니다.

판매처별 리포트와 같이 **전 채널**을 봅니다. 고객·상품별 리포트(식별 가능
채널)와 분모가 다릅니다.
"""

import os

import master as M
import ledger as L
import reportlib as R

OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'chart.js')

MEASURES = [dict(key='qty', label='수량', kind=R.KIND_INT),
            dict(key='val', label='금액', kind=R.KIND_KRW)]
PERIODS  = [dict(key='mtd', label='당월'),
            dict(key='ytd', label='누적 (YTD)')]


def _index(rows):
    """[measure][line][channel][ym] 으로 접습니다."""
    cell = dict(qty={}, val={})
    for r in rows:
        for key, v in (('qty', r.qty), ('val', r.amount)):
            d = cell[key].setdefault(r.line, {}).setdefault(r.channel, {})
            d[r.ym()] = d.get(r.ym(), 0) + v
    return cell


def _ytd(by_ym, ym):
    """그 해 1월부터 ym 까지의 누계. 해가 바뀌면 리셋됩니다."""
    total = 0
    for m in range(1, ym[1] + 1):
        total += by_ym.get((ym[0], m), 0)
    return total


def _row_defs():
    """ALL → 카테고리 → 제품라인 3단. 원본의 SUMMARY 계층 그대로입니다."""
    defs = [dict(key='*', label='ALL', indent=0, total=True)]
    for cat in M.CATEGORIES:
        defs.append(dict(key='cat:' + cat, label=cat, indent=1))
        for line in M.LINES:
            if line['cat'] != cat:
                continue
            defs.append(dict(key=line['code'], indent=2,
                             label='%s %s' % (line['code'], line['name'])))
    return defs


def _lines_of(key):
    if key == '*':
        return [l['code'] for l in M.LINES]
    if key.startswith('cat:'):
        return [l['code'] for l in M.LINES if l['cat'] == key[4:]]
    return [key]


def _series(cell, measure, line_keys, channel_keys):
    """선택한 라인 × 채널 조합의 월별 합계."""
    out = {}
    src = cell[measure]
    for lc in line_keys:
        for ch in channel_keys:
            for ym, v in src.get(lc, {}).get(ch, {}).items():
                out[ym] = out.get(ym, 0) + v
    return out


def build(rows, customers):
    cell = _index(rows)
    months = M.WINDOW_13
    calc_months = M.month_range(M.shift_month(months[0], -12), months[-1])
    row_defs = _row_defs()
    ch_keys = M.CHANNEL_KEYS
    base = M.BASE_MONTH

    # ── 교차표 ───────────────────────────────────────────────────────
    # 행 = 제품라인 계층, 열 = 채널. 원본의 방향 그대로입니다.
    cross = {}
    for meas in MEASURES:
        for per in PERIODS:
            grid = []
            for rd in row_defs:
                lks = _lines_of(rd['key'])
                line_vals = []
                for ch in ch_keys:
                    s = _series(cell, meas['key'], lks, [ch])
                    line_vals.append(_ytd(s, base) if per['key'] == 'ytd'
                                     else s.get(base, 0))
                grid.append(line_vals)
            cross['%s|%s' % (meas['key'], per['key'])] = grid

    # ── 추이 ─────────────────────────────────────────────────────────
    def trend_rows(meas, per, axis):
        out = []
        if axis == 'line':
            defs = row_defs
        elif axis == 'cat':
            defs = [d for d in row_defs if d['indent'] < 2]
        else:
            defs = ([dict(key='*', label='ALL', indent=0, total=True)] +
                    [dict(key='ch:' + c['key'], label=c['key'], indent=1,
                          note='%s / %s · %s' % (c['group'], c['sub'], c['model']),
                          inactive=(c['status'] == 'INACTIVE'))
                     for c in M.CHANNELS])
        for d in defs:
            if d['key'].startswith('ch:'):
                s = _series(cell, meas['key'], _lines_of('*'), [d['key'][3:]])
            else:
                s = _series(cell, meas['key'], _lines_of(d['key']), ch_keys)
            if per['key'] == 'ytd':
                s = dict((ym, _ytd(s, ym)) for ym in calc_months)
            r = R.row(d['label'], meas['kind'], s, note=d.get('note'))
            r['indent'] = d['indent']
            if d.get('total'):
                r['total'] = True
            if d.get('inactive'):
                r['inactive'] = True
            out.append(r)
        return out

    trends = {}
    for meas in MEASURES:
        for per in PERIODS:
            k = '%s|%s' % (meas['key'], per['key'])
            trends[k] = dict(
                line=trend_rows(meas, per, 'line'),
                cat=trend_rows(meas, per, 'cat'),
                channel=trend_rows(meas, per, 'channel'),
            )

    return dict(
        title='Chart 리포트',
        base=M.month_key(base),
        months=R.month_labels(),
        measures=MEASURES,
        periods=PERIODS,
        channels=[dict(key=c['key'], group=c['group'], sub=c['sub'],
                       model=c['model'], inactive=(c['status'] == 'INACTIVE'))
                  for c in M.CHANNELS],
        row_defs=row_defs,
        cross=cross,
        trends=trends,
        notes=[
            '교차표의 칸 농담은 **행 안에서만** 계산합니다 — 제품라인끼리 '
            '크기를 견주는 색이 아니라, 각 라인이 어느 채널에서 팔리는지를 '
            '찾는 색입니다. 농도는 알파로만 조절해 글자가 읽히는 밝기를 '
            '유지합니다.',
            'MTD 는 기준월 한 달, YTD 는 그 해 1월부터 기준월까지의 누계입니다. '
            'YTD 추이는 해가 바뀌면 리셋되므로 1월에 떨어집니다 — 누계선의 '
            '정상 동작입니다.',
            '전 채널을 봅니다 — 고객·상품별 리포트(식별 가능 채널)와 분모가 다릅니다.',
            '금액은 sell-out(소비자 판매가) 기준입니다. 판매처별 리포트의 '
            'sell-in 과 섞지 마세요.',
        ],
    )


def check(payload):
    """교차표의 행·열 합이 서로 맞는지 봅니다.

    계층 합계(ALL / 카테고리)를 따로 더하면 라인 합과 어긋나기 쉽습니다.
    표에서는 '반올림 차이' 처럼 보여 눈으로는 안 걸립니다.
    """
    row_defs = payload['row_defs']
    idx = dict((d['key'], i) for i, d in enumerate(row_defs))
    for key, grid in payload['cross'].items():
        # ALL 행 = 카테고리 행들의 합
        allrow = grid[idx['*']]
        for ci in range(len(allrow)):
            s = sum(grid[idx['cat:' + c]][ci] for c in M.CATEGORIES)
            assert s == allrow[ci], (
                '%s: ALL 행과 카테고리 합이 %d번째 열에서 어긋납니다 (%s vs %s)'
                % (key, ci, format(allrow[ci], ','), format(s, ',')))
        # 카테고리 행 = 그 안 라인들의 합
        for cat in M.CATEGORIES:
            crow = grid[idx['cat:' + cat]]
            codes = [l['code'] for l in M.LINES if l['cat'] == cat]
            for ci in range(len(crow)):
                s = sum(grid[idx[c]][ci] for c in codes)
                assert s == crow[ci], (
                    '%s: %s 행과 라인 합이 %d번째 열에서 어긋납니다' % (key, cat, ci))

    # 교차표(MTD) 총합 = 같은 조합 추이표의 ALL 행 마지막 달
    for meas in payload['measures']:
        k = '%s|mtd' % meas['key']
        grid_total = sum(payload['cross'][k][idx['*']])
        trend_all = payload['trends'][k]['line'][0]['values'][-1]
        assert grid_total == trend_all, (
            '%s: 교차표 총합 %s 과 추이표 ALL %s 이 다릅니다'
            % (k, format(grid_total, ','), format(trend_all, ',')))
    return True


def main():
    rows, customers = L.build_calibrated()
    payload = build(rows, customers)
    check(payload)
    out = os.path.abspath(OUT)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    n = R.js_file(out, 'CHART_DATA', payload, payload['title'])
    print('data/chart.js  %s bytes  (교차 %d조합 · 행 %d · 열 %d)'
          % (format(n, ','), len(payload['cross']),
             len(payload['row_defs']), len(payload['channels'])))


if __name__ == '__main__':
    main()
