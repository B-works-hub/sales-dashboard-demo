# -*- coding: utf-8 -*-
"""리포트 공통 — 13개월 매트릭스와 증감 계산.

원본 리포트 5종이 공유하는 문법이 하나 있습니다.

    직전 13개월 × 지표  +  월평균  +  전월대비(증감수·성장률)
                                    +  전년동월대비(증감수·성장률)

이 모양을 리포트마다 다시 짜면 어느 하나에서 분모가 달라지고, 그때부터
'이 리포트가 틀렸다'는 말이 나옵니다. 여기 한 번만 둡니다.

증감 표기 규칙도 같이 정합니다 — 비중(%) 지표는 뺄셈으로 %p 를 내고,
금액·수량 지표는 나눗셈으로 % 를 냅니다. 비중을 나눠서 % 로 내면
'10% → 12%' 가 20% 증가로 보입니다. 원본은 이걸 %p 로 구분합니다.
"""

import master as M

# 지표 종류 — 포맷과 증감 계산 방식을 결정합니다.
KIND_INT   = 'int'      # 사람 수, 건수
KIND_KRW   = 'krw'      # 금액
KIND_PCT   = 'pct'      # 비중 → 증감은 %p
KIND_DAYS  = 'days'     # 일수
KIND_FLOAT = 'float'    # 평균 횟수 등


def series(values_by_month, months=None):
    """월별 dict → 리포트 한 줄. 없는 달은 None 으로 둡니다(0 이 아닙니다)."""
    months = months or M.WINDOW_13
    return [values_by_month.get(ym) for ym in months]


def mean(vals):
    """월평균 — 값이 있는 달만 나눕니다.

    빈 달을 분모에 넣으면 채널이 늦게 열린 달까지 나눠 평균이 낮아집니다.
    0 은 실적이므로 넣고, None 은 '아직 없음'이므로 뺍니다.
    """
    got = [v for v in vals if v is not None]
    if not got:
        return None
    return sum(got) / float(len(got))


def delta(cur, prev, kind):
    """증감수. 비중 지표는 비워 둡니다.

    비중의 '증감수'와 '성장률'은 둘 다 cur - prev 라 같은 값이 두 번
    나옵니다. 원본 시트도 비중 행은 증감수를 비우고 %p 만 적습니다.
    """
    if kind == KIND_PCT:
        return None
    if cur is None or prev is None:
        return None
    return cur - prev


def growth(cur, prev, kind):
    """성장률. 비중 지표는 %p 차이를, 나머지는 배율을 냅니다.

    분모가 0 이면 성장률이 정의되지 않습니다. 무한대나 0% 로 적어 넘기지
    않고 None 을 돌려보내 화면에 '-' 로 나오게 합니다.
    """
    if cur is None or prev is None:
        return None
    if kind == KIND_PCT:
        return cur - prev            # %p
    if not prev:
        return None
    return (cur - prev) / float(prev)


def row(name, kind, values_by_month, note=None, months=None):
    """리포트 한 줄 전체 — 값 13개 + 월평균 + 전월대비 + 전년동월대비."""
    months = months or M.WINDOW_13
    vals = series(values_by_month, months)
    cur  = vals[-1]
    prev = vals[-2] if len(vals) > 1 else None
    yoy  = values_by_month.get(M.shift_month(months[-1], -12))
    return dict(
        name=name, kind=kind, values=vals, avg=mean(vals),
        mom_delta=delta(cur, prev, kind), mom_growth=growth(cur, prev, kind),
        yoy_delta=delta(cur, yoy, kind),  yoy_growth=growth(cur, yoy, kind),
        note=note,
    )


# 비율을 낼 최소 분모. 이보다 표본이 작으면 값을 내지 않습니다.
#
# 라인 구매 고객이 3명인 달에 2명이 재구매하면 66.7% 로 찍힙니다. 옆 달은
# 0% 고, 그 사이 증감은 ▲66.7%p 가 됩니다. 신호가 아니라 잡음인데 표에서는
# 가장 큰 숫자로 보입니다. 작은 제품라인에서 이런 칸이 줄줄이 나옵니다.
MIN_DEN = 20


def ratio_row(name, num_by_month, den_by_month, note=None, months=None,
              min_den=None):
    """비중 줄 — 분자/분모를 받아 직접 나눕니다.

    비중의 월평균을 '월별 비중의 평균'으로 내면 분모가 작은 달이 과대
    반영됩니다. 합계끼리 나눈 값을 씁니다.

    min_den 미만인 달은 None 으로 비웁니다. 0% 로 적으면 '실적이 0' 과
    '표본이 모자람' 이 같은 칸으로 보입니다.
    """
    months = months or M.WINDOW_13
    floor = MIN_DEN if min_den is None else min_den
    by, thin = {}, 0
    for ym in months + [M.shift_month(months[-1], -12)]:
        n, d = num_by_month.get(ym), den_by_month.get(ym)
        if n is None or not d:
            by[ym] = None
        elif d < floor:
            by[ym] = None
            if ym in months:
                thin += 1
        else:
            by[ym] = n / float(d)
    r = row(name, KIND_PCT, by, note=note, months=months)
    num_tot = sum(v for v in (num_by_month.get(m) for m in months) if v is not None)
    den_tot = sum(v for v in (den_by_month.get(m) for m in months) if v is not None)
    r['avg'] = (num_tot / float(den_tot)) if den_tot >= floor else None
    r['thin'] = thin          # 표본 부족으로 비운 달 수
    return r


def month_labels(months=None):
    months = months or M.WINDOW_13
    return [dict(y=y, m=m, key=M.month_key((y, m))) for (y, m) in months]


def js_file(path, varname, payload, title):
    """data/*.js 로 씁니다. JSON 을 var 하나에 담아 script 태그로 읽습니다.

    fetch 를 쓰면 file:// 로 열었을 때 CORS 로 막힙니다. 저장소를 clone 해
    더블클릭으로 열어보는 경로를 살려 둡니다.
    """
    import json
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'),
                      default=_default)
    with open(path, 'w') as f:
        f.write('/* %s — tools/ 의 생성기가 만든 가상 데이터입니다.\n'
                ' * 실제 매출·거래처·상품은 한 줄도 들어 있지 않습니다. */\n'
                % title)
        f.write('var %s = %s;\n' % (varname, body))
    return len(body)


def _default(o):
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(repr(o))


def selftest():
    assert mean([1, 2, None, 3]) == 2.0
    assert mean([None, None]) is None
    assert growth(12, 10, KIND_INT) == 0.2
    assert growth(0.12, 0.10, KIND_PCT) - 0.02 < 1e-9   # %p
    assert growth(5, 0, KIND_INT) is None               # 분모 0 → 정의 안 됨
    assert delta(None, 3, KIND_INT) is None
    mm = [(2026, 6), (2026, 7)]
    r = ratio_row('t', {(2026, 7): 1, (2026, 6): 9},
                  {(2026, 7): 100, (2026, 6): 100}, months=mm)
    assert abs(r['avg'] - 0.05) < 1e-9, r['avg']        # 10/200, 비중 평균이 아님
    # 표본이 모자란 달은 0% 가 아니라 빈칸이어야 합니다
    t = ratio_row('t', {(2026, 7): 2, (2026, 6): 40},
                  {(2026, 7): 3, (2026, 6): 100}, months=mm)
    assert t['values'][-1] is None, t['values']
    assert t['thin'] == 1, t['thin']
    assert t['mom_growth'] is None                      # 빈칸에서 증감을 내지 않음
    return 'ok'


if __name__ == '__main__':
    print(selftest())
