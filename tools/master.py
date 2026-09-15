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
#   sellin     : 공급가율 — sell-in ÷ sell-out 의 연 누적 기준값.
#                직영도 1.0 이 아닙니다. 소비자가에서 결제수수료·부가세가
#                빠진 금액이 우리 장부에 잡힙니다. 위탁은 판매수수료가,
#                직매입은 도매 마진이 더 빠집니다.
CHANNELS = [
    # 온라인 · 직영몰
    dict(key='자사몰',        group='온라인',   sub='직영몰', model='직영',   opened='2021.04', closed=None,      status='ACTIVE',   weight=0.150, bulk=1,  sellin=0.90),
    dict(key='검색포털 I',    group='온라인',   sub='직영몰', model='직영',   opened='2021.04', closed=None,      status='ACTIVE',   weight=0.045, bulk=1,  sellin=0.91),
    # 온라인 · 입점몰
    dict(key='오픈마켓 A',    group='온라인',   sub='입점몰', model='위탁',   opened='2021.04', closed=None,      status='ACTIVE',   weight=0.190, bulk=1,  sellin=0.85),
    dict(key='오픈마켓 B',    group='온라인',   sub='입점몰', model='직매입', opened='2023.02', closed=None,      status='ACTIVE',   weight=0.080, bulk=1,  sellin=0.85),
    dict(key='편집숍 C',      group='온라인',   sub='입점몰', model='위탁',   opened='2021.06', closed=None,      status='ACTIVE',   weight=0.035, bulk=1,  sellin=0.85),
    dict(key='신선몰 J',      group='온라인',   sub='입점몰', model='직매입', opened='2022.03', closed=None,      status='ACTIVE',   weight=0.050, bulk=1,  sellin=0.85),
    dict(key='기타온몰 K',    group='온라인',   sub='입점몰', model='위탁',   opened='2021.05', closed=None,      status='ACTIVE',   weight=0.020, bulk=1,  sellin=0.85),
    dict(key='라이브커머스 F', group='온라인',  sub='입점몰', model='위탁',   opened='2022.09', closed=None,      status='ACTIVE',   weight=0.030, bulk=2,  sellin=0.85),
    dict(key='구도몰 O',      group='온라인',   sub='입점몰', model='위탁',   opened='2023.06', closed='2025.05', status='INACTIVE', weight=0.000, bulk=1,  sellin=0.85),
    # 오프라인 · 매장
    dict(key='플래그십',      group='오프라인', sub='매장',   model='직영',   opened='2024.03', closed=None,      status='ACTIVE',   weight=0.070, bulk=1,  sellin=0.92),
    dict(key='직영매장 G',    group='오프라인', sub='매장',   model='직영',   opened='2022.05', closed=None,      status='ACTIVE',   weight=0.025, bulk=1,  sellin=0.92),
    dict(key='팝업스토어 L',  group='오프라인', sub='매장',   model='직영',   opened='2023.08', closed=None,      status='ACTIVE',   weight=0.020, bulk=1,  sellin=0.92),
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

# 고객을 사람 단위로 식별할 수 있는 채널.
#
# 대량주문·사입·어매니티·면세·수출은 받는 쪽이 법인이거나 중간 유통이라
# '이 사람이 이 제품라인을 경험했다'를 셀 수 없습니다. 상품별·고객 리포트의
# 경험률·재구매 지표는 여기 있는 채널만 봅니다. 매출 집계(판매처별·Chart)는
# 전 채널을 그대로 씁니다 — 두 리포트의 분모가 다른 이유입니다.
IDENTIFIED_CHANNELS = [c['key'] for c in CHANNELS
                       if c['group'] == '온라인' or c['sub'] == '매장']

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
# 원본 리포트의 카테고리 체계입니다. ACCESSORIES 와 OTHER 는 제품이 아니라
# 파우치·기프트백·에디션 같은 부속과 그 밖의 항목을 담는 자리인데, 매출에는
# 잡히므로 빼면 총계가 안 맞습니다.
CATEGORIES = ['HOME CARE', 'MIND CARE', 'HAND CARE', 'HAIR & BODY',
              'ACCESSORIES', 'OTHER']

LINES = [
    dict(code='MSP', name='멀티스프레이',   cat='HOME CARE',   weight=0.28, refill=True),
    dict(code='ASP', name='공간스프레이',   cat='HOME CARE',   weight=0.06, refill=True),
    dict(code='LDT', name='세탁세제',       cat='HOME CARE',   weight=0.08, refill=True),
    dict(code='RMS', name='룸스프레이',     cat='MIND CARE',   weight=0.13, refill=False),
    dict(code='SCH', name='향낭',           cat='MIND CARE',   weight=0.05, refill=False),
    dict(code='EPL', name='아이필로우',     cat='MIND CARE',   weight=0.02, refill=False),
    dict(code='AOL', name='아로마오일',     cat='MIND CARE',   weight=0.04, refill=False),
    dict(code='HWS', name='핸드워시',       cat='HAND CARE',   weight=0.07, refill=True),
    dict(code='HBM', name='핸드밤',         cat='HAND CARE',   weight=0.06, refill=False),
    dict(code='SOP', name='비누',           cat='HAIR & BODY', weight=0.04, refill=False),
    dict(code='BWS', name='바디워시',       cat='HAIR & BODY', weight=0.05, refill=True),
    dict(code='BLT', name='바디로션',       cat='HAIR & BODY', weight=0.04, refill=True),
    dict(code='SHP', name='샴푸',           cat='HAIR & BODY', weight=0.02, refill=True),
    dict(code='CDT', name='컨디셔너',       cat='HAIR & BODY', weight=0.02, refill=False),
    dict(code='ACC', name='부속',           cat='ACCESSORIES', weight=0.03, refill=False),
    dict(code='ETC', name='기타',           cat='OTHER',       weight=0.01, refill=False),
]

LINE_BY_CODE = dict((l['code'], l) for l in LINES)


# 변형 그룹 — 원본은 라인 아래에 refill / bottle 한 단을 더 둡니다.
# 리필을 본품과 나란히 놓으면 '본품을 산 사람이 리필까지 갔는가' 가 표에서
# 안 보입니다. 그래서 한 단을 더 씁니다.
VARIANTS = ['bottle', 'refill', 'set']

VARIANT_LABEL = {'bottle': '본품', 'refill': '리필', 'set': '세트'}


def _skus():
    """단품 SKU. 라인마다 본품 / 리필 / (일부) 세트를 깝니다.

    variant 가 원본의 refill·bottle 계층 자리이고, 가격은 전부 가상입니다.
    """
    base = {
        'MSP': [('본품 300ml', 32000, 'bottle'), ('리필 450ml', 26000, 'refill'),
                ('리필 900ml', 45000, 'refill'), ('기프트 세트', 58000, 'set')],
        'ASP': [('본품 110ml', 29000, 'bottle'), ('리필 500ml', 24000, 'refill')],
        'LDT': [('본품 1.2L', 34000, 'bottle'), ('리필 1.6L', 28000, 'refill')],
        'RMS': [('110ml', 59000, 'bottle'), ('50ml', 39000, 'bottle'),
                ('기프트 세트', 88000, 'set')],
        'SCH': [('싱글', 19000, 'bottle'), ('키트', 22000, 'set')],
        'EPL': [('베이직', 42000, 'bottle')],
        'AOL': [('7ml', 36000, 'bottle'), ('15ml', 62000, 'bottle')],
        'HWS': [('본품 450ml', 42000, 'bottle'), ('리필 900ml', 56000, 'refill')],
        'HBM': [('35ml', 25000, 'bottle'), ('핸드 세트', 49000, 'set')],
        'SOP': [('90g', 29000, 'bottle'), ('3입 세트', 76000, 'set')],
        'BWS': [('450ml', 43000, 'bottle'), ('리필 900ml', 58000, 'refill')],
        'BLT': [('300ml', 41000, 'bottle'), ('리필 700ml', 55000, 'refill')],
        'SHP': [('450ml', 39000, 'bottle'), ('리필 800ml', 52000, 'refill')],
        'CDT': [('450ml', 39000, 'bottle')],
        'ACC': [('파우치 S', 12000, 'bottle'), ('파우치 M', 18000, 'bottle'),
                ('기프트백 L', 9000, 'bottle'), ('세라믹 홀더', 46000, 'bottle')],
        'ETC': [('시즌 에디션', 88000, 'bottle'), ('사이즈업 할인', 15000, 'bottle')],
    }
    out = []
    for line in LINES:
        for i, (variant, price, vg) in enumerate(base[line['code']], 1):
            out.append(dict(
                sku='%s-%02d' % (line['code'], i * 10),
                line=line['code'], cat=line['cat'], variant=vg,
                name='%s %s' % (line['name'], variant),
                price=price, is_refill=(vg == 'refill'), is_gift=(vg == 'set'),
                is_bundle=False,
            ))
    return out


def _bundles():
    """세트 상품 — 원본의 DETAILS 구획입니다.

    여러 라인을 묶은 상품이라 '어느 라인의 매출인가' 가 하나로 안 정해집니다.
    원본이 단품(SUMMARY)과 세트(DETAILS)를 아예 다른 구획으로 나눠 놓은
    이유이고, 여기서도 대표 라인만 달아 두고 구획을 분리합니다.
    """
    spec = [
        ('MSP', [('450ml 세트', 58000), ('900ml 세트', 92000), ('기프트 세트', 74000),
                 ('차량용 세트', 46000), ('반려동물 세트', 52000), ('모닝리추얼 세트', 68000)]),
        ('ASP', [('공간 세트', 54000), ('리필 2입 세트', 44000)]),
        ('LDT', [('세탁 세트', 60000), ('대용량 2입', 52000)]),
        ('RMS', [('룸스프레이 2종 세트', 98000), ('미니 3종 세트', 72000),
                 ('시즌 한정 세트', 118000)]),
        ('SCH', [('향낭 키트', 38000), ('향낭 리필 세트', 30000)]),
        ('AOL', [('오일 2종 세트', 86000)]),
        ('HWS', [('핸드 듀오', 66000), ('핸드 케어 세트', 84000)]),
        ('HBM', [('핸드밤 3입', 66000), ('트래블 키트', 42000)]),
        ('SOP', [('솝 12입', 108000), ('미니 솝 세트', 34000)]),
        ('BWS', [('바디 듀오', 78000), ('바디 풀세트', 124000)]),
        ('BLT', [('로션 2입', 74000)]),
        ('SHP', [('헤어 듀오', 72000), ('헤어 풀세트', 96000)]),
        ('ACC', [('기프트 패키지 S', 28000), ('기프트 패키지 L', 54000)]),
        ('ETC', [('면세 세트', 82000), ('B2B 대량 세트', 140000)]),
    ]
    out = []
    n = 0
    for code, items in spec:
        line = LINE_BY_CODE[code]
        for name, price in items:
            n += 1
            out.append(dict(
                sku='S%04d' % (n * 7), line=code, cat=line['cat'], variant='set',
                name='%s %s' % (line['name'], name), price=price,
                is_refill=False, is_gift=True, is_bundle=True,
            ))
    return out


SINGLES = _skus()          # 원본 SUMMARY 구획
BUNDLES = _bundles()       # 원본 DETAILS 구획
SKUS = SINGLES + BUNDLES
SKU_BY_CODE = dict((s['sku'], s) for s in SKUS)


# ── 플래그십 매장 ───────────────────────────────────────────────────
# 국적은 실제 관광 통계에서도 흔한 구분이라 일반명사로 둡니다.
NATIONS   = ['일본', '대만', '중국', '싱가포르', '미국', '그 외']

# 수출 채널의 도착국. 플래그십 방문객의 국적과는 다른 축입니다 — 하나는
# 매장에 온 사람, 하나는 물건이 나간 나라입니다. 원본도 YTD 구간에서만
# 이 분해를 답니다.
EXPORT_NATIONS = ['싱가포르', '일본', '대만', '홍콩', '미국']
WEEKDAYS  = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
HOURS     = ['%02d:00-%02d:00' % (h, h + 1) for h in range(10, 20)]

# ── 고객 ────────────────────────────────────────────────────────────
AGE_BANDS = ['14세이하', '15-24', '25-34', '35-44', '45-54', '55-64', '65이상', '정보없음']
AGE_MIX   = [0.001, 0.03, 0.20, 0.24, 0.15, 0.04, 0.01, 0.329]


def selftest():
    assert len(CHANNELS) == len(set(CHANNEL_KEYS)), '채널 키 중복'
    assert len(LINES) == 16, '제품라인은 16개'
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
    idw = sum(c['weight'] for c in CHANNELS if c['key'] in IDENTIFIED_CHANNELS)
    assert 0.6 < idw < 0.8, '식별 가능 채널 비중이 %.2f' % idw
    assert len(SKUS) == len(set(s['sku'] for s in SKUS)), 'SKU 중복'
    # 리필 라인으로 선언해 놓고 리필 SKU 가 없으면 '리필구매연결비율' 이
    # 조용히 0% 로 나옵니다. 지표가 0 인 건지 제품이 없는 건지 화면에서
    # 구분이 안 되므로 여기서 막습니다.
    for l in LINES:
        has = any(s['is_refill'] for s in SINGLES if s['line'] == l['code'])
        assert has == l['refill'], \
            '%s: refill=%s 인데 리필 SKU 는 %s' % (l['code'], l['refill'], has)
    # 카테고리마다 라인이 최소 하나는 있어야 계층이 빈 칸으로 끊기지 않습니다
    for c in CATEGORIES:
        assert any(l['cat'] == c for l in LINES), '%s 에 라인이 없습니다' % c
    # 변형 그룹은 셋뿐입니다 — 새 값이 들어오면 계층 렌더가 조용히 빠뜨립니다
    bad = set(s['variant'] for s in SKUS) - set(VARIANTS)
    assert not bad, '모르는 변형 그룹: %s' % bad
    # 세트는 DETAILS 구획으로만 갑니다
    assert all(s['is_bundle'] for s in BUNDLES)
    assert not any(s['is_bundle'] for s in SINGLES)
    return dict(months=len(ALL_MONTHS), channels=len(CHANNELS),
                categories=len(CATEGORIES), lines=len(LINES),
                singles=len(SINGLES), bundles=len(BUNDLES))


if __name__ == '__main__':
    print(selftest())
