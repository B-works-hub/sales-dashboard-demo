# -*- coding: utf-8 -*-
"""가상 마스터 — 채널·제품·기간.

월간 리포트 5종이 모두 이 마스터를 읽습니다. 채널 목록이나 제품 코드를
리포트마다 따로 두면 판매처별 리포트의 '자사몰 7월'과 Chart 의 '자사몰 7월'이
어긋나고, 그 순간 데모가 자기모순이 됩니다.

이름은 전부 가상입니다. 실물 운영본의 판매처명·제품명·내부 라인코드는
한 자도 들어 있지 않습니다. 표기 계열은 일일 대시보드(daily/)와 맞췄습니다 —
'오픈마켓 A' 처럼 업태 + 알파벳.
"""

import datetime as dt

# ── 기간 ────────────────────────────────────────────────────────────
# 리포트가 '전년 동월 대비'를 내려면 기준월보다 한 해 앞이 있어야 하고,
# '직전 13개월'을 그리려면 거기서 13개월이 더 있어야 합니다.
# 기준월 2026-07 → 최소 2024-07. 그런데 원장이 막 시작한 구간은 채널이
# 차례로 열리고 고객 풀이 차오르는 '램프업'이라, 그게 창 안에 들어오면
# 전년동월대비가 +130% 같은 값으로 새어 나옵니다. 한 해 더 앞에서 시작해
# 비교 대상이 되는 해는 이미 안정된 상태이도록 둡니다.
LEDGER_START = (2023, 1)
BASE_MONTH   = (2026, 7)      # 리포트 기준월
MONTHS_BACK  = 13             # 직전 13개월 매트릭스


def month_range(start, end):
    """(y, m) 튜플을 start 부터 end 까지 순서대로."""
    y, m = start
    out = []
    while (y, m) <= end:
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def shift_month(ym, delta):
    y, m = ym
    i = y * 12 + (m - 1) + delta
    return (i // 12, i % 12 + 1)


def month_key(ym):
    return '%04d-%02d' % ym


def days_in_month(ym):
    y, m = ym
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - dt.date(y, m, 1)).days


ALL_MONTHS   = month_range(LEDGER_START, BASE_MONTH)
WINDOW_13    = month_range(shift_month(BASE_MONTH, -(MONTHS_BACK - 1)), BASE_MONTH)


# ── 채널 ────────────────────────────────────────────────────────────
# 원본 리포트의 계층(온라인 > 직영몰/입점몰, 오프라인, 글로벌)을 그대로 옮기되
# 이름만 가상입니다. weight 는 매출 편중, seasonality 는 월별 가중입니다.
#   key        : 데이터 안에서 쓰는 식별자
#   group      : 온라인 / 오프라인 / 글로벌
#   sub        : 계층 2단
#   model      : 직영 / 위탁 / 직매입 / 기타   (판매처별 리포트의 model 열)
#   opened     : 입점시기
#   closed     : 거래 종료월 (None 이면 진행 중)
#   status     : ACTIVE / INACTIVE
#   weight     : 목표 '매출' 비중.  주문 빈도가 아닙니다 — 대량주문은 건수가
#                적고 건당이 크므로, 주문 빈도는 weight ÷ bulk 로 역산합니다.
#                이걸 섞으면 대량주문이 매출의 절반을 먹습니다.
#   bulk       : 건당 평균 수량 배수 (1 = 일반 소비자 주문)
#   sellin     : sell-in ÷ sell-out 비율 (직영은 1.0 — 사입이 없음)
CHANNELS = [
    # 온라인 · 직영몰
    dict(key='자사몰',        group='온라인',   sub='직영몰', model='직영',   opened='2021.04', closed=None,      status='ACTIVE',   weight=0.150, bulk=1,  sellin=1.00),
    dict(key='검색포털 I',    group='온라인',   sub='직영몰', model='직영',   opened='2021.04', closed=None,      status='ACTIVE',   weight=0.045, bulk=1,  sellin=1.00),
    # 온라인 · 입점몰
    dict(key='오픈마켓 A',    group='온라인',   sub='입점몰', model='위탁',   opened='2021.04', closed=None,      status='ACTIVE',   weight=0.190, bulk=1,  sellin=0.85),
    dict(key='오픈마켓 B',    group='온라인',   sub='입점몰', model='직매입', opened='2023.02', closed=None,      status='ACTIVE',   weight=0.080, bulk=1,  sellin=0.85),
    dict(key='편집숍 C',      group='온라인',   sub='입점몰', model='위탁',   opened='2021.06', closed=None,      status='ACTIVE',   weight=0.035, bulk=1,  sellin=0.85),
    dict(key='신선몰 J',      group='온라인',   sub='입점몰', model='직매입', opened='2022.03', closed=None,      status='ACTIVE',   weight=0.050, bulk=1,  sellin=0.85),
    dict(key='기타온몰 K',    group='온라인',   sub='입점몰', model='위탁',   opened='2021.05', closed=None,      status='ACTIVE',   weight=0.020, bulk=1,  sellin=0.85),
    dict(key='라이브커머스 F', group='온라인',  sub='입점몰', model='위탁',   opened='2022.09', closed=None,      status='ACTIVE',   weight=0.030, bulk=2,  sellin=0.85),
    dict(key='구도몰 O',      group='온라인',   sub='입점몰', model='위탁',   opened='2023.06', closed='2025.05', status='INACTIVE', weight=0.000, bulk=1,  sellin=0.85),
    # 오프라인 · 매장
    dict(key='플래그십',      group='오프라인', sub='매장',   model='직영',   opened='2024.03', closed=None,      status='ACTIVE',   weight=0.070, bulk=1,  sellin=1.00),
    dict(key='직영매장 G',    group='오프라인', sub='매장',   model='직영',   opened='2022.05', closed=None,      status='ACTIVE',   weight=0.025, bulk=1,  sellin=1.00),
    dict(key='팝업스토어 L',  group='오프라인', sub='매장',   model='직영',   opened='2023.08', closed=None,      status='ACTIVE',   weight=0.020, bulk=1,  sellin=1.00),
    # 오프라인 · 유통
    dict(key='백화점 D',      group='오프라인', sub='유통',   model='위탁',   opened='2022.11', closed=None,      status='ACTIVE',   weight=0.040, bulk=1,  sellin=0.80),
    dict(key='복지몰 H',      group='오프라인', sub='유통',   model='위탁',   opened='2022.02', closed=None,      status='ACTIVE',   weight=0.030, bulk=3,  sellin=0.80),
    dict(key='대량주문',      group='오프라인', sub='유통',   model='기타',   opened='2021.09', closed=None,      status='ACTIVE',   weight=0.060, bulk=24, sellin=0.75),
    dict(key='사입',          group='오프라인', sub='유통',   model='직매입', opened='2021.12', closed=None,      status='ACTIVE',   weight=0.020, bulk=8,  sellin=0.70),
    dict(key='어매니티',      group='오프라인', sub='유통',   model='기타',   opened='2023.04', closed=None,      status='ACTIVE',   weight=0.010, bulk=30, sellin=0.75),
    # 글로벌
    dict(key='면세 E',        group='글로벌',   sub='면세',   model='직매입', opened='2023.05', closed=None,      status='ACTIVE',   weight=0.025, bulk=6,  sellin=0.70),
    dict(key='수출',          group='글로벌',   sub='수출',   model='직매입', opened='2025.11', closed=None,      status='ACTIVE',   weight=0.100, bulk=40, sellin=0.65),
]

CHANNEL_KEYS = [c['key'] for c in CHANNELS]
ACTIVE_CHANNELS = [c for c in CHANNELS if c['status'] == 'ACTIVE']

# 주문 빈도 가중치 — 매출 비중을 건당 수량으로 나눈 값입니다.
_freq_raw = dict((c['key'], c['weight'] / float(c['bulk'])) for c in CHANNELS)
_freq_sum = sum(_freq_raw.values())
for _c in CHANNELS:
    _c['freq'] = _freq_raw[_c['key']] / _freq_sum

# 목표 연매출(원). 원본 리포트의 자릿수를 따라가야 '천원' 단위 표기가
# 의미를 갖습니다. ledger.py 가 이 값에 맞춰 주문 수를 보정합니다.
TARGET_ANNUAL_KRW = 4_300_000_000

# 일일 대시보드(daily/)가 쓰는 판매처 이름 — 월간 원장이 이를 포함하는지
# 검증하는 데 씁니다. 두 데모의 표기를 어긋나지 않게 두기 위한 것이고,
# 합계까지 맞추지는 않습니다(원장이 서로 다릅니다).
DAILY_CHANNEL_NAMES = [
    '자사몰', '오픈마켓 A', '오픈마켓 B', '편집숍 C',
    '백화점 D', '면세 E', '라이브커머스 F', '직영매장 G', '복지몰 H',
]


# ── 제품 ────────────────────────────────────────────────────────────
# 카테고리 4 > 라인 14 > SKU. 라인 코드는 제품 유형의 영문 약어이고,
# 어떤 브랜드의 내부 코드도 아닙니다.
CATEGORIES = ['HOME CARE', 'FRAGRANCE', 'HAND CARE', 'HAIR & BODY']

LINES = [
    dict(code='MSP', name='멀티스프레이',   cat='HOME CARE',   weight=0.30, refill=True),
    dict(code='ASP', name='공간스프레이',   cat='HOME CARE',   weight=0.06, refill=True),
    dict(code='LDT', name='세탁세제',       cat='HOME CARE',   weight=0.09, refill=True),
    dict(code='RMS', name='룸스프레이',     cat='FRAGRANCE',   weight=0.14, refill=False),
    dict(code='SCH', name='향낭',           cat='FRAGRANCE',   weight=0.05, refill=False),
    dict(code='EPL', name='아이필로우',     cat='FRAGRANCE',   weight=0.02, refill=False),
    dict(code='AOL', name='아로마오일',     cat='FRAGRANCE',   weight=0.04, refill=False),
    dict(code='HWS', name='핸드워시',       cat='HAND CARE',   weight=0.07, refill=True),
    dict(code='HBM', name='핸드밤',         cat='HAND CARE',   weight=0.06, refill=False),
    dict(code='SOP', name='비누',           cat='HAIR & BODY', weight=0.04, refill=False),
    dict(code='BWS', name='바디워시',       cat='HAIR & BODY', weight=0.05, refill=True),
    dict(code='BLT', name='바디로션',       cat='HAIR & BODY', weight=0.04, refill=True),
    dict(code='SHP', name='샴푸',           cat='HAIR & BODY', weight=0.02, refill=True),
    dict(code='CDT', name='컨디셔너',       cat='HAIR & BODY', weight=0.02, refill=False),
]

LINE_BY_CODE = dict((l['code'], l) for l in LINES)


def _skus():
    """라인마다 본품 / 리필 / 세트를 깝니다. 가격은 전부 가상입니다."""
    base = {
        'MSP': [('본품 300ml', 32000), ('리필 450ml', 26000), ('리필 900ml', 45000), ('기프트 세트', 58000)],
        'ASP': [('본품 110ml', 29000), ('리필 500ml', 24000)],
        'LDT': [('본품 1.2L', 34000), ('리필 1.6L', 28000)],
        'RMS': [('110ml', 59000), ('50ml', 39000), ('기프트 세트', 88000)],
        'SCH': [('싱글', 19000), ('키트', 22000)],
        'EPL': [('베이직', 42000)],
        'AOL': [('7ml', 36000), ('15ml', 62000)],
        'HWS': [('본품 450ml', 42000), ('리필 900ml', 56000)],
        'HBM': [('35ml', 25000), ('핸드 세트', 49000)],
        'SOP': [('90g', 29000), ('3입 세트', 76000)],
        'BWS': [('450ml', 43000), ('리필 900ml', 58000)],
        'BLT': [('300ml', 41000), ('리필 700ml', 55000)],
        'SHP': [('450ml', 39000)],
        'CDT': [('450ml', 39000)],
    }
    out = []
    for line in LINES:
        for i, (variant, price) in enumerate(base[line['code']], 1):
            out.append(dict(
                sku='%s-%02d' % (line['code'], i * 10),
                line=line['code'],
                cat=line['cat'],
                name='%s %s' % (line['name'], variant),
                price=price,
                is_refill='리필' in variant,
                is_gift='세트' in variant,
            ))
    return out


SKUS = _skus()
SKU_BY_CODE = dict((s['sku'], s) for s in SKUS)


# ── 플래그십 매장 ───────────────────────────────────────────────────
# 국적은 실제 관광 통계에서도 흔한 구분이라 일반명사로 둡니다.
NATIONS   = ['일본', '대만', '중국', '싱가포르', '미국', '그 외']
WEEKDAYS  = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
HOURS     = ['%02d:00-%02d:00' % (h, h + 1) for h in range(10, 20)]

# ── 고객 ────────────────────────────────────────────────────────────
AGE_BANDS = ['14세이하', '15-24', '25-34', '35-44', '45-54', '55-64', '65이상', '정보없음']
AGE_MIX   = [0.001, 0.03, 0.20, 0.24, 0.15, 0.04, 0.01, 0.329]


def selftest():
    assert len(CHANNELS) == len(set(CHANNEL_KEYS)), '채널 키 중복'
    assert len(LINES) == 14, '제품라인은 14개'
    assert abs(sum(l['weight'] for l in LINES) - 1.0) < 1e-9, '라인 가중치 합이 1이 아님'
    assert abs(sum(c['weight'] for c in CHANNELS) - 1.0) < 1e-9, '채널 가중치 합이 1이 아님'
    assert abs(sum(c['freq'] for c in CHANNELS) - 1.0) < 1e-9, '빈도 가중치 합이 1이 아님'
    for c in CHANNELS:
        if c['closed']:
            assert c['status'] == 'INACTIVE', '%s: 종료월이 있는데 ACTIVE' % c['key']
    assert abs(sum(AGE_MIX) - 1.0) < 1e-9, '연령 분포 합이 1이 아님'
    missing = [n for n in DAILY_CHANNEL_NAMES if n not in CHANNEL_KEYS]
    assert not missing, '일일 대시보드 판매처가 월간 마스터에 없음: %s' % missing
    assert len(WINDOW_13) == 13
    assert len(SKUS) == len(set(s['sku'] for s in SKUS)), 'SKU 중복'
    return dict(months=len(ALL_MONTHS), channels=len(CHANNELS),
                lines=len(LINES), skus=len(SKUS))


if __name__ == '__main__':
    print(selftest())
