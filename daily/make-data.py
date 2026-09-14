#!/usr/bin/env python3
"""데모판에 심을 가상 매출 데이터를 만든다.

    python tools/make-data.py > demo-data.js

**전부 지어낸 숫자다.** 실제 회사 데이터는 한 줄도 들어가지 않는다.
브랜드·판매처·상품 이름도 모두 가상이다.

대시보드가 시트에서 읽는 표를 그대로 흉내 낸다. 첫 줄이 머리글이고 그 아래가
자료 줄이라, 화면 쪽 코드는 시트를 읽을 때와 똑같이 동작한다.

숫자는 눈에 그럴듯해야 한다. 난수만 뿌리면 그래프가 톱니처럼 보이고 표의
증감률이 의미 없는 값으로 채워진다. 그래서 아래를 넣는다.

  · 요일 주기      주말이 낮고 월요일이 높다
  · 완만한 성장    뒤로 갈수록 조금씩 커진다
  · 채널 편중      자사몰이 크고 나머지가 붙는다
  · 기획전 구간    특정 기간에 특정 라인이 튄다
  · 작년 같은 기간 '작년 동기간 대비'가 빈칸이 되지 않게 13개월치를 만든다
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date, timedelta

# ── 가상의 설정 ────────────────────────────────────────────────
# 순서가 곧 화면 표시 순서이자 색 순서다.
CHANNELS = [
    ("자사몰", 1.00),
    ("오픈마켓 A", 0.62),
    ("오픈마켓 B", 0.48),
    ("편집숍 C", 0.30),
    ("백화점 D", 0.26),
    ("면세 E", 0.22),
    ("라이브커머스 F", 0.18),
    ("직영매장 G", 0.14),
    ("복지몰 H", 0.09),
]

# 제품라인 코드 → (표시 이름, 상품들)
LINES = {
    "AAA": ("아로마 디퓨저", [
        ("AAA-101", "아로마 디퓨저 200ml", 38000),
        ("AAA-102", "아로마 디퓨저 리필 200ml", 24000),
        ("AAA-110", "아로마 디퓨저 기프트 세트", 52000),
    ]),
    "BBB": ("핸드케어", [
        ("BBB-201", "핸드워시 300ml", 22000),
        ("BBB-202", "핸드크림 50ml", 18000),
        ("BBB-210", "핸드케어 듀오 세트", 36000),
    ]),
    "CCC": ("룸스프레이", [
        ("CCC-301", "룸스프레이 100ml", 29000),
        ("CCC-302", "룸스프레이 미니 30ml", 14000),
    ]),
    "DDD": ("바디케어", [
        ("DDD-401", "바디워시 400ml", 26000),
        ("DDD-402", "바디로션 300ml", 28000),
    ]),
}

# 기획전 — (이름, 시작, 일수, 대상 라인, 매출 배수)
def promotions(last: date) -> list[tuple]:
    return [
        ("봄맞이 홈프레그런스", last - timedelta(days=150), 10, "AAA", 3.2),
        ("핸드케어 위크", last - timedelta(days=74), 7, "BBB", 2.8),
        ("룸스프레이 신규 런칭", last - timedelta(days=26), 9, "CCC", 2.0),
    ]


def weekday_factor(d: date) -> float:
    # 월요일이 높고 주말이 낮다
    return [1.12, 1.05, 1.00, 0.98, 1.02, 0.82, 0.74][d.weekday()]


def season_factor(d: date) -> float:
    # 완만한 연중 물결 — 연말이 조금 높다
    return 1.0 + 0.12 * math.sin((d.timetuple().tm_yday / 365.0) * 2 * math.pi - 1.2)


def build(last: date, months: int, seed: int) -> dict:
    rnd = random.Random(seed)
    first = last - timedelta(days=int(months * 30.4))
    promos = promotions(last)

    매출행 = [["날짜", "제품라인", "상품코드", "상품명", "정상가",
              "채널명", "수량", "매출", "promo"]]

    day = first
    while day <= last:
        # 하루 전체 규모. 뒤로 갈수록 완만하게 커진다.
        진행 = (day - first).days / max(1, (last - first).days)
        기본 = 3_200_000 * (0.80 + 0.75 * 진행)
        규모 = 기본 * weekday_factor(day) * season_factor(day) * rnd.uniform(0.86, 1.16)

        오늘기획 = ""
        배수라인 = None
        배수 = 1.0
        for 이름, 시작, 일수, 라인, 곱 in promos:
            if 시작 <= day < 시작 + timedelta(days=일수):
                오늘기획, 배수라인, 배수 = 이름, 라인, 곱
                break

        for 채널, 비중 in CHANNELS:
            # 채널마다 쉬는 날이 있다 — 빈칸이 있어야 일평균 규칙이 드러난다
            if 비중 < 0.2 and rnd.random() < 0.35:
                continue
            채널규모 = 규모 * 비중 * rnd.uniform(0.85, 1.15)

            for 라인, (_, 상품들) in LINES.items():
                라인배수 = 배수 if 라인 == 배수라인 else 1.0
                if rnd.random() < (0.12 if 라인배수 == 1.0 else 0.02):
                    continue
                for 코드, 이름, 정가 in 상품들:
                    if rnd.random() < 0.30:
                        continue
                    몫 = 채널규모 / (len(LINES) * len(상품들)) * 라인배수
                    수량 = max(1, round(몫 / 정가 * rnd.uniform(0.7, 1.4)))
                    할인 = rnd.choice([1.0, 1.0, 1.0, 0.95, 0.9])
                    매출 = round(수량 * 정가 * 할인 / 10) * 10
                    매출행.append([
                        day.isoformat(), 라인, 코드, 이름, 정가,
                        채널, 수량, 매출,
                        오늘기획 if 라인 == 배수라인 else "",
                    ])
        day += timedelta(days=1)

    # ── 메모 ───────────────────────────────────────────────
    메모 = [["날짜", "판매처", "제품라인", "상품코드", "메모"]]
    메모 += [
        [(last - timedelta(days=3)).isoformat(), "자사몰", "", "",
         "쿠폰 오적용으로 일부 주문 취소 — 재집계 예정"],
        [(last - timedelta(days=5)).isoformat(), "오픈마켓 A", "", "",
         "직매입 물량 반영분 포함. 전주 대비 증가는 일시적입니다."],
        [(last - timedelta(days=21)).isoformat(), "자사몰", "CCC", "",
         "룸스프레이 런칭일 — 라이브 방송 동시 진행"],
        [(last - timedelta(days=9)).isoformat(), "직영매장 G", "", "",
         "정기휴무"],
        [(last - timedelta(days=12)).isoformat(), "합계", "", "",
         "전사 프로모션 종료일"],
    ]

    # ── 한 줄 코멘트 ───────────────────────────────────────
    코멘트 = [["날짜", "comments"], [
        last.isoformat(),
        "룸스프레이 런칭 3주차 — 자사몰 비중이 계속 오르고 있습니다.",
    ]]

    # ── 설정 ───────────────────────────────────────────────
    설정 = [["구분", "값", "값2"]]
    설정 += [["판매처", c, ""] for c, _ in CHANNELS]
    설정 += [["라인힌트", 이름.replace(" ", ""), 코드] for 코드, (이름, _) in LINES.items()]
    설정 += [["판매처별칭", "일일총주문금액", "합계"], ["판매처별칭", "총합계", "합계"]]
    설정 += [["제품군", 이름, 코드] for 코드, (이름, _) in LINES.items()]

    # 리뷰 탭이 쓰는 표들 — 위에서 만든 매출행에서 파생시킨다
    일별매출 = {}
    for r in 매출행[1:]:
        일별매출[r[0]] = 일별매출.get(r[0], 0) + r[7]
    리뷰, 리뷰메모 = review_tables(last, rnd, 일별매출)
    유입 = visit_table(last, months, rnd, 일별매출)
    일자별요약, 주문라인요약 = order_tables(last, rnd, 매출행, 4)

    return {"일일매출정보": 매출행, "메모": 메모, "플로팅코멘트": 코멘트, "설정": 설정,
            "리뷰": 리뷰, "리뷰메모": 리뷰메모, "유입": 유입,
            "일자별요약": 일자별요약, "주문라인요약": 주문라인요약}



# ══════════════════════════════════════════════════════════════
#  프로모션 리뷰 탭이 읽는 표들
#  ── 리뷰 시트(발신·고객 입력값) + 주문 원장 요약 두 벌 + 유입 로그
# ══════════════════════════════════════════════════════════════

RV_HEAD = [
    "프로모션명", "전략시작일", "전략종료일", "행사기간", "제품라인", "제품",
    "발신타겟", "구매채널", "전략내용", "전략타입", "전략타입(세부)",
    "비회원구매가능여부", "적립금중복사용가능여부",
    "타겟모수", "발신채널", "발신일", "발신시각", "발신모수", "열람수", "클릭수",
    "유입고객수", "구매고객수", "-신규고객수", "-기존고객수",
    "판매상품수량(전략상품)", "전략상품코드", "행사품목+추가구매품목매출", "비교대상",
]

# 발신 한 건 — (타겟, 채널, 시작일로부터 며칠째, 시각, 타겟모수, 발신비율, 열람률, 클릭률)
SENDS = {
    "봄맞이 홈프레그런스": [
        ("전체 회원", "앱 푸시", 0, 0.4166, 41200, 0.94, 0.31, 0.11),
        ("구매 고객", "문자", 0, 0.5416, 12800, 0.98, None, 0.09),
    ],
    "핸드케어 위크": [
        ("전체 회원", "앱 푸시", 0, 0.4375, 43900, 0.95, 0.29, 0.13),
        ("휴면 고객", "문자", 2, 0.4583, 9600, 0.97, None, 0.06),
    ],
    "룸스프레이 신규 런칭": [
        ("전체 회원", "앱 푸시", 0, 0.4166, 46300, 0.96, 0.34, 0.16),
        ("구매 고객", "이메일", 0, 0.4583, 18400, 0.92, 0.41, 0.22),
        ("관심 등록", "문자", 3, 0.5000, 7300, 0.99, None, 0.12),
    ],
}

STRATEGY = {
    "봄맞이 홈프레그런스": ("15% 할인 + 5만원 이상 사은품", "할인", "정률 할인"),
    "핸드케어 위크": ("2개 구매 시 1개 증정", "증정", "N+1"),
    "룸스프레이 신규 런칭": ("신제품 런칭가 + 리뷰 적립금 2배", "런칭", "런칭가"),
}


def review_tables(last: date, rnd: random.Random, 일별매출: dict) -> tuple:
    """리뷰 시트와 리뷰 메모 표를 만든다. 매출·고객수는 화면이 원장에서 다시 계산하므로
    여기 값은 원장이 그 기간을 못 덮을 때 쓰는 대비용이다."""
    rows = [RV_HEAD]
    비교 = {"룸스프레이 신규 런칭": "핸드케어 위크"}

    for 이름, 시작, 일수, 라인, _곱 in promotions(last):
        종료 = 시작 + timedelta(days=일수 - 1)
        표시이름, 상품들 = LINES[라인]
        전략, 타입, 세부 = STRATEGY[이름]
        코드 = ", ".join(c for c, _, _ in 상품들)
        기간매출 = sum(v for d, v in 일별매출.items() if 시작.isoformat() <= d <= 종료.isoformat())
        구매고객 = max(1, round(기간매출 / 88000))
        신규 = round(구매고객 * rnd.uniform(0.22, 0.34))

        for 타겟, 채널, 오프셋, 시각, 타겟모수, 발신율, 열람률, 클릭률 in SENDS[이름]:
            발신 = round(타겟모수 * 발신율)
            열람 = round(발신 * 열람률) if 열람률 else ""
            클릭 = round((열람 if 열람 else 발신) * 클릭률)
            rows.append([
                이름, 시작.isoformat(), 종료.isoformat(), f"{일수}일", 라인, 표시이름,
                타겟, "자사몰", 전략, 타입, 세부, "가능", "불가",
                타겟모수, 채널, (시작 + timedelta(days=오프셋)).isoformat(), 시각,
                발신, 열람, 클릭, 클릭,
                구매고객, 신규, 구매고객 - 신규,
                "", 코드, "", 비교.get(이름, ""),
            ])

    메모 = [["프로모션명", "전략시작일", "항목", "발신채널", "발신일", "메모", "작성일", "작성자"]]
    시작들 = {이름: 시작 for 이름, 시작, _, _, _ in promotions(last)}
    메모 += [
        ["룸스프레이 신규 런칭", 시작들["룸스프레이 신규 런칭"].isoformat(), "",
         "", "", "런칭 첫날 라이브 방송을 함께 돌려 유입이 평소의 세 배였습니다.",
         (last - timedelta(days=20)).isoformat(), "운영팀"],
        ["룸스프레이 신규 런칭", 시작들["룸스프레이 신규 런칭"].isoformat(), "클릭률",
         "이메일", (시작들["룸스프레이 신규 런칭"]).isoformat(),
         "제목에 가격을 넣은 안이 이겼습니다 — 다음 발신에도 적용",
         (last - timedelta(days=19)).isoformat(), "운영팀"],
        ["핸드케어 위크", 시작들["핸드케어 위크"].isoformat(), "행사기간매출",
         "", "", "둘째 날 재고 소진으로 반나절 판매 중단",
         (last - timedelta(days=70)).isoformat(), "운영팀"],
    ]
    return rows, 메모


def visit_table(last: date, months: int, rnd: random.Random, 일별매출: dict) -> list:
    """유입(방문) 일자별. 매출이 큰 날 방문도 많게 묶어 둔다."""
    rows = [["날짜", "방문고객수", "처음방문", "재방문", "신규회원수"]]
    for d in sorted(일별매출):
        매출 = 일별매출[d]
        방문 = round(매출 / 3400 * rnd.uniform(0.9, 1.1))
        처음 = round(방문 * rnd.uniform(0.34, 0.44))
        rows.append([d, 방문, 처음, 방문 - 처음, round(처음 * rnd.uniform(0.10, 0.18))])
    return rows


def order_tables(last: date, rnd: random.Random, 매출행: list, 주문개월: int) -> tuple:
    """주문 원장 요약 두 벌. 자사몰만 담는다 (실물도 자사몰 전용).

    일일매출 원본은 하루·채널·상품 단위로 접힌 표라, 그대로는 '주문'이 없다.
    그래서 하루치를 낱개로 펼친 뒤 다시 주문으로 묶는다. 이렇게 해야 구매고객수와
    객단가가 매출과 아귀가 맞는다 — 접힌 표를 그대로 쓰면 고객 수가 터무니없이
    적게 잡히고 객단가가 수십만 원으로 뛴다.

    일자별요약은 전 기간, 주문라인요약은 최근 몇 달만 만든다. 오래된 기획전이
    '원장 범위 밖이라 시트 입력값을 씁니다' 로 떨어지는 모습도 함께 보여준다.
    """
    일자별 = [["주문일", "제품라인", "상품코드", "매출", "수량"]]
    주문라인 = [["주문일", "주문번호", "주문자휴대전화", "주문자ID", "첫구매",
                "제품라인", "상품코드", "상품명", "매출", "수량"]]
    # 주문번호·고객키는 화면에 안 나오고 묶는 데만 쓰이므로 짧게 적는다

    원장시작 = (last - timedelta(days=int(주문개월 * 30.4))).isoformat()
    하루치 = {}
    for r in 매출행[1:]:
        if r[5] != "자사몰":
            continue
        하루치.setdefault(r[0], []).append(r)

    주문번호 = 100000
    고객수 = 9000
    첫구매본적 = set()

    for 날 in sorted(하루치):
        낱개 = []
        for r in 하루치[날]:
            _날, 라인코드, 코드, 이름, _정가, _채널, 수량, 매출, _promo = r
            # 마감 반영분 — 취소·환불이 빠져 잠정치보다 조금 작다
            마감 = round(매출 * rnd.uniform(0.93, 0.99) / 10) * 10
            일자별.append([날, 라인코드, 코드, 마감, 수량])
            if 날 < 원장시작:
                continue
            단가 = 마감 / max(1, 수량)
            for _ in range(수량):
                낱개.append((라인코드, 코드, 이름, round(단가 / 10) * 10))

        if not 낱개:
            continue
        rnd.shuffle(낱개)

        # 낱개를 주문으로 묶는다 — 한 주문에 1~4개
        i = 0
        while i < len(낱개):
            묶음 = 낱개[i:i + rnd.choice([1, 1, 1, 2, 2, 3, 4])]
            i += len(묶음)
            주문번호 += 1
            키 = "c%d" % rnd.randint(1, 고객수)
            첫 = ""
            if 키 not in 첫구매본적:
                첫구매본적.add(키)
                if rnd.random() < 0.45:
                    첫 = "첫주문"
            # 같은 상품이 한 주문에 여러 개면 한 줄로 합친다
            합 = {}
            for 라인코드, 코드, 이름, 금액 in 묶음:
                key = (라인코드, 코드, 이름)
                수, 액 = 합.get(key, (0, 0))
                합[key] = (수 + 1, 액 + 금액)
            for (라인코드, 코드, 이름), (수, 액) in 합.items():
                주문라인.append([날, "O%d" % 주문번호, 키,
                               "u%s" % 키[1:], 첫,
                               라인코드, 코드, 이름, 액, 수])

    return 일자별, 주문라인


def main() -> int:
    p = argparse.ArgumentParser(description="데모용 가상 매출 데이터 생성")
    p.add_argument("--last", default="2026-08-18", help="마지막 날짜 (YYYY-MM-DD)")
    p.add_argument("--months", type=int, default=14, help="며칠치를 만들지 (개월)")
    p.add_argument("--seed", type=int, default=7, help="같은 값이면 같은 결과")
    args = p.parse_args()

    tables = build(date.fromisoformat(args.last), args.months, args.seed)
    rows = sum(len(t) - 1 for t in tables.values())

    out = [
        "/* 데모용 가상 데이터 — tools/make-data.py 로 만들었습니다.",
        " * 실제 매출·거래처·상품은 한 줄도 들어 있지 않습니다. */",
        "var DEMO_DATA = " + json.dumps(tables, ensure_ascii=False, separators=(",", ":")) + ";",
        f"/* 자료 {rows:,}줄 · 기준일 {args.last} */",
    ]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
