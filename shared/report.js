/* 월간 리포트 공통 — 포맷터 · 매트릭스 렌더 · CSV · URL 상태
 *
 * ES5 로 씁니다. 일일 대시보드와 같은 제약이고, 빌드 단계가 없습니다.
 *
 * 표기 규칙 하나만 지키면 나머지는 따라옵니다 —
 *   비중(%) 지표의 증감은 뺄셈으로 %p,  금액·수량 지표는 나눗셈으로 %.
 * 비중을 나눠서 % 로 내면 '10% → 12%' 가 20% 증가로 보입니다.
 */
var Report = (function () {
  'use strict';

  /* ── 포맷 ─────────────────────────────────────────────────────── */

  function comma(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function fmt(v, kind) {
    if (v === null || v === undefined) return '–';
    switch (kind) {
      case 'krw':   return '₩' + comma(Math.round(v));
      case 'pct':   return (v * 100).toFixed(1) + '%';
      case 'days':  return comma(Math.round(v));
      case 'float': return (Math.round(v * 10) / 10).toFixed(1);
      default:      return comma(Math.round(v));
    }
  }

  /* 증감수. 비중은 %p, 금액은 ₩, 나머지는 수. 부호를 항상 답니다. */
  function fmtDelta(v, kind) {
    if (v === null || v === undefined) return '–';
    var sign = v > 0 ? '' : (v < 0 ? '-' : '');
    var a = Math.abs(v);
    if (kind === 'pct')  return sign + (a * 100).toFixed(1) + '%p';
    if (kind === 'krw')  return sign + '₩' + comma(Math.round(a));
    if (kind === 'float') return sign + (Math.round(a * 10) / 10).toFixed(1);
    return sign + comma(Math.round(a));
  }

  /* 성장률. 비중 지표는 growth 가 이미 %p 차이로 들어옵니다. */
  function fmtGrowth(v, kind) {
    if (v === null || v === undefined) return '–';
    var mark = v > 0 ? '▲' : (v < 0 ? '▼' : '');
    var a = Math.abs(v) * 100;
    // %p 는 소수 한 자리를 답니다. 버리면 '-0.2%p' 가 '0%p▼' 로 나와
    // 방향 표시와 숫자가 서로 어긋나 보입니다.
    if (kind === 'pct') return a.toFixed(1) + '%p' + mark;
    return (a >= 1000 ? comma(Math.round(a)) : a.toFixed(0)) + '%' + mark;
  }

  /* 오르면 붉게, 내리면 푸르게 — 국내 재무 표기 관행입니다. */
  function dirClass(v) {
    if (v === null || v === undefined) return 'nil';
    if (v > 0) return 'up';
    if (v < 0) return 'down';
    return 'flat';
  }

  /* ── 매트릭스 표 ──────────────────────────────────────────────── */

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  function renderMatrix(section, months) {
    var table = el('table');
    var last = months.length - 1;

    /* 섹션 전체가 비중 지표면 증감수 열이 통째로 비어 나옵니다(비중의
       증감은 %p 하나로 충분해 delta 를 내지 않습니다). 빈 열 두 개가
       19열 중 2열을 먹으므로 아예 접습니다. */
    var allPct = section.rows.length > 0;
    for (var q = 0; q < section.rows.length; q++) {
      if (section.rows[q].kind !== 'pct') { allPct = false; break; }
    }
    var cmpSpan = allPct ? 1 : 2;

    /* 머리 2줄 — 연도 / 월. 같은 해는 한 번만 적습니다. */
    var thead = el('thead');
    var rY = el('tr', 'years');
    rY.appendChild(el('th', 'metric', ''));
    var i, prevY = null;
    for (i = 0; i < months.length; i++) {
      var th = el('th', i === last ? 'cur' : '', months[i].y !== prevY ? months[i].y + '년' : '');
      prevY = months[i].y;
      rY.appendChild(th);
    }
    rY.appendChild(el('th', 'avg', ''));
    var g1 = el('th', 'grp cmp', '전월대비'); g1.colSpan = cmpSpan; rY.appendChild(g1);
    var g2 = el('th', 'grp cmp', '전년동월대비'); g2.colSpan = cmpSpan; rY.appendChild(g2);
    thead.appendChild(rY);

    var rM = el('tr');
    rM.appendChild(el('th', 'metric', '지표'));
    for (i = 0; i < months.length; i++) {
      rM.appendChild(el('th', i === last ? 'cur' : '', months[i].m + '월'));
    }
    rM.appendChild(el('th', 'avg', '월평균'));
    if (!allPct) rM.appendChild(el('th', 'cmp', '증감수'));
    rM.appendChild(el('th', 'cmp', allPct ? '증감(%p)' : '성장률'));
    if (!allPct) rM.appendChild(el('th', 'cmp', '증감수'));
    rM.appendChild(el('th', 'cmp', allPct ? '증감(%p)' : '성장률'));
    thead.appendChild(rM);
    table.appendChild(thead);

    var tbody = el('tbody');
    for (var r = 0; r < section.rows.length; r++) {
      var row = section.rows[r];
      var isRatio = row.name.charAt(0) === '(' || /비중|비율|률$/.test(row.name);
      var tr = el('tr', isRatio ? 'is-ratio' : (/^총/.test(row.name) ? 'is-total' : ''));

      if (row.total) tr.className = 'is-total';
      if (row.inactive) tr.className += ' is-inactive';

      var th = el('th', 'metric');
      th.scope = 'row';
      th.textContent = row.name;
      if (row.note) th.title = row.note;
      /* 계층 들여쓰기. 비중 행의 들여쓰기와 겹치면 안 되므로 인라인으로
         덮어씁니다 — 판매처별 리포트는 그룹 > 하위 > 채널 3단입니다. */
      if (row.indent) th.style.paddingLeft = (10 + row.indent * 15) + 'px';
      tr.appendChild(th);

      for (i = 0; i < row.values.length; i++) {
        var td = el('td', 'num' + (i === last ? ' cur' : ''), fmt(row.values[i], row.kind));
        if (row.values[i] === null || row.values[i] === undefined) td.className += ' nil';
        tr.appendChild(td);
      }
      tr.appendChild(el('td', 'num avg', fmt(row.avg, row.kind)));
      if (!allPct) {
        tr.appendChild(el('td', 'num cmp ' + dirClass(row.mom_delta), fmtDelta(row.mom_delta, row.kind)));
      }
      tr.appendChild(el('td', 'num cmp ' + dirClass(row.mom_growth), fmtGrowth(row.mom_growth, row.kind)));
      if (!allPct) {
        tr.appendChild(el('td', 'num cmp ' + dirClass(row.yoy_delta), fmtDelta(row.yoy_delta, row.kind)));
      }
      tr.appendChild(el('td', 'num cmp ' + dirClass(row.yoy_growth), fmtGrowth(row.yoy_growth, row.kind)));
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    return table;
  }

  /* ── 교차 히트맵 ──────────────────────────────────────────────────
     행 = 제품라인 계층, 열 = 채널.

     농담은 **행 안에서만** 계산합니다. 표 전체를 한 척도로 칠하면 큰 라인이
     전부 진하고 작은 라인이 전부 연해져, 이미 왼쪽 숫자로 아는 사실을
     색으로 한 번 더 말할 뿐입니다. 행별로 나누면 '이 라인이 어느 채널에서
     팔리는가' 라는, 숫자만 봐서는 안 보이는 것이 나옵니다.

     색은 한 가지 색상의 밝기 한 단계뿐이고(무지개 아님), 농도는 알파로만
     조절해 글자가 흰색으로 바뀔 만큼 어두워지지 않습니다. */

  function renderCross(grid, rowDefs, cols, kind, colMeta) {
    var table = el('table', 'heat');
    var i, j;

    var thead = el('thead');
    var rg = el('tr', 'years');
    rg.appendChild(el('th', 'metric', ''));
    var prevGroup = null, span = 0, pending = null;
    for (i = 0; i < cols.length; i++) {
      var g = colMeta && colMeta[i] ? colMeta[i].group : '';
      if (g === prevGroup) { span++; }
      else {
        if (pending) { pending.colSpan = span; rg.appendChild(pending); }
        pending = el('th', 'grp', g); span = 1; prevGroup = g;
      }
    }
    if (pending) { pending.colSpan = span; rg.appendChild(pending); }
    rg.appendChild(el('th', 'avg', ''));
    thead.appendChild(rg);

    var rh = el('tr');
    rh.appendChild(el('th', 'metric', '제품라인'));
    for (i = 0; i < cols.length; i++) {
      var th = el('th', colMeta && colMeta[i] && colMeta[i].inactive ? 'nil' : '', cols[i]);
      rh.appendChild(th);
    }
    rh.appendChild(el('th', 'avg', '합계'));
    thead.appendChild(rh);
    table.appendChild(thead);

    var tbody = el('tbody');
    for (i = 0; i < rowDefs.length; i++) {
      var def = rowDefs[i], vals = grid[i];
      var tr = el('tr', def.total ? 'is-total' : '');
      var th = el('th', 'metric');
      th.scope = 'row';
      th.textContent = def.label;
      if (def.indent) th.style.paddingLeft = (10 + def.indent * 15) + 'px';
      tr.appendChild(th);

      var rowMax = 0, rowSum = 0;
      for (j = 0; j < vals.length; j++) {
        rowSum += vals[j];
        if (vals[j] > rowMax) rowMax = vals[j];
      }
      for (j = 0; j < vals.length; j++) {
        var td = el('td', 'num cell', fmt(vals[j], kind));
        if (!vals[j]) {
          td.className += ' nil';
        } else {
          /* 0~1 정규화 값만 심고 알파 범위는 CSS 가 테마별로 매핑합니다.
             여기서 알파를 계산해 굳혀 두면 다크에서 칸이 너무 밝아져
             흰 글자 대비가 3.87:1 까지 떨어지고, 테마를 바꿔도 다시
             칠해지지 않습니다. */
          td.className += ' on';
          td.style.setProperty('--t', (vals[j] / rowMax).toFixed(4));
          td.title = def.label + ' · ' + cols[j] + '\n' + fmt(vals[j], kind) +
                     ' · 행 내 ' + (100 * vals[j] / rowSum).toFixed(1) + '%';
        }
        tr.appendChild(td);
      }
      tr.appendChild(el('td', 'num avg', fmt(rowSum, kind)));
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    return table;
  }

  /* 스케일 범례 — 농담이 무엇을 뜻하는지 적지 않으면 색이 장식이 됩니다. */
  function heatLegend() {
    var wrap = el('div', 'heat-legend');
    wrap.appendChild(el('span', '', '행 내 비중'));
    var bar = el('span', 'heat-bar');
    for (var i = 0; i < 6; i++) {
      var sw = el('span', 'heat-sw');
      sw.style.setProperty('--t', (i / 5).toFixed(2));
      bar.appendChild(sw);
    }
    wrap.appendChild(bar);
    wrap.appendChild(el('span', '', '낮음 → 높음'));
    return wrap;
  }

  /* ── CSV ──────────────────────────────────────────────────────── */

  function csvCell(s) {
    s = (s === null || s === undefined) ? '' : String(s);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  /* 원시값을 냅니다 — ▲▼ 나 ₩ 를 넣으면 받는 쪽에서 다시 벗겨야 합니다. */
  function toCsv(section, months) {
    var head = ['지표'];
    for (var i = 0; i < months.length; i++) head.push(months[i].key);
    head = head.concat(['월평균', '전월대비 증감수', '전월대비 성장률',
                        '전년동월대비 증감수', '전년동월대비 성장률', '정의']);
    var lines = [head.map(csvCell).join(',')];
    for (var r = 0; r < section.rows.length; r++) {
      var row = section.rows[r];
      var line = [row.name].concat(row.values, [
        row.avg, row.mom_delta, row.mom_growth,
        row.yoy_delta, row.yoy_growth, row.note || '']);
      lines.push(line.map(csvCell).join(','));
    }
    return '﻿' + lines.join('\n');       // BOM — 엑셀에서 한글이 깨집니다
  }

  function crossCsv(grid, rowDefs, cols) {
    var lines = [['제품라인'].concat(cols, ['합계']).map(csvCell).join(',')];
    for (var i = 0; i < rowDefs.length; i++) {
      var sum = 0;
      for (var j = 0; j < grid[i].length; j++) sum += grid[i][j];
      lines.push([rowDefs[i].label].concat(grid[i], [sum]).map(csvCell).join(','));
    }
    return '\ufeff' + lines.join('\n');
  }

  function download(name, text) {
    var blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  /* ── URL 상태 ─────────────────────────────────────────────────── */

  function readState(key, fallback) {
    var m = new RegExp('[?&]' + key + '=([^&]*)').exec(location.search);
    return m ? decodeURIComponent(m[1]) : fallback;
  }

  function writeState(key, value) {
    var params = [];
    var q = location.search.replace(/^\?/, '');
    if (q) {
      var parts = q.split('&');
      for (var i = 0; i < parts.length; i++) {
        if (parts[i] && parts[i].split('=')[0] !== key) params.push(parts[i]);
      }
    }
    params.push(key + '=' + encodeURIComponent(value));
    history.replaceState(null, '', location.pathname + '?' + params.join('&'));
  }

  /* ── 원본 시트 표 (품목별 판매 현황) ──────────────────────────────
     327행 × 245열짜리 시트를 그대로 옮긴 표입니다. 매트릭스·히트맵과 달리
     여기서는 **읽기 좋게 고치지 않는 것**이 목적입니다 — 원본을 쓰던 사람이
     같은 자리에서 같은 숫자를 찾을 수 있어야 합니다.

     다만 두 가지는 바꿉니다.
       · 라벨을 왼쪽에 고정 — 원본은 155열, 표 한가운데입니다. 종이에서는
         되지만 가로 스크롤에서는 이름이 화면 밖으로 나갑니다.
       · 계층을 들여쓰기로 — 원본은 굵기로만 구분해 4단이 한 칸에 겹칩니다.

     `shr` 은 싣지 않고 여기서 나눕니다. 분모는 언제나 **그 기간 ALL 행의
     값**이라 값 하나당 한 번의 나눗셈이면 되고, 파일이 절반으로 줄어듭니다. */

  function wideCols(D, opt) {
    var cols = [];
    var C = D.cols, i;

    function pair(m, per, label, blk, field, idx, den, cls) {
      var t;
      for (t = 0; t < 2; t++) {
        cols.push({ m: m, per: per, g3: label, blk: blk, f: field, i: idx,
                    den: den, cls: cls || '', t: t ? 's' : 'v' });
      }
    }
    function grow(m, per, label, blk, now, was) {
      cols.push({ m: m, per: per, g3: label, blk: blk, now: now, was: was,
                  cls: 'cmp', t: 'g' });
    }

    var MEAS = [{ k: 'qty', label: '수량' }, { k: 'val', label: '금액' }];
    for (var mi = 0; mi < MEAS.length; mi++) {
      var m = MEAS[mi].label, mk = MEAS[mi].k;
      var mtd = mk + '|mtd', ytd = mk + '|ytd';

      pair(m, 'MTD', C.py, mtd, 'py', null, 'py');
      pair(m, 'MTD', C.cur, mtd, 'cur', null, 'cur', 'cur');
      if (opt.ch) {
        for (i = 0; i < D.channels.length; i++) {
          pair(m, 'MTD', D.channels[i].key, mtd, 'cur_ch', i, 'cur',
               D.channels[i].inactive ? 'off' : '');
        }
      }
      grow(m, 'MTD', 'YoY', mtd, 'cur', 'py');
      pair(m, 'MTD', C.pm, mtd, 'pm', null, 'pm');
      /* 금액 MTD 의 전월에는 채널 분해가 없습니다 — 원본 그대로입니다. */
      if (opt.ch && D.grid[mtd].pm_ch) {
        for (i = 0; i < D.channels.length; i++) {
          pair(m, 'MTD', D.channels[i].key, mtd, 'pm_ch', i, 'pm',
               D.channels[i].inactive ? 'off' : '');
        }
      }
      grow(m, 'MTD', 'MoM', mtd, 'cur', 'pm');

      pair(m, 'YTD', C.y_all, ytd, 'y_all', null, 'y_all');
      pair(m, 'YTD', C.y_ytd, ytd, 'y_ytd', null, 'y_ytd');
      pair(m, 'YTD', C.cur, ytd, 'cur', null, 'cur', 'cur');
      if (opt.ch) {
        for (i = 0; i < D.channels.length; i++) {
          pair(m, 'YTD', D.channels[i].key, ytd, 'cur_ch', i, 'cur',
               D.channels[i].inactive ? 'off' : '');
        }
      }
      if (opt.nat) {
        for (i = 0; i < D.nations.length; i++) {
          pair(m, 'YTD', D.nations[i], ytd, 'cur_nat', i, 'cur', 'nat');
        }
      }
      grow(m, 'YTD', 'YoY', ytd, 'cur', 'y_ytd');
    }
    return cols;
  }

  function wideRaw(D, c, r) {
    var b = D.grid[c.blk];
    if (c.t === 'g') {
      var was = b[c.was][r], now = b[c.now][r];
      return was ? now / was - 1 : null;
    }
    var v = (c.i === null || c.i === undefined) ? b[c.f][r] : b[c.f][r][c.i];
    if (c.t === 'v') return v;
    var den = b[c.den][0];
    return den ? v / den : null;
  }

  function wideText(D, c, r) {
    var v = wideRaw(D, c, r);
    if (c.t === 'g') return v === null ? '–' : fmtGrowth(v, 'int');
    if (c.t === 's') return (v === null || v === 0) ? '–' : v.toFixed(2);
    if (!v) return '–';
    return fmt(v, c.m === '금액' ? 'krw' : 'int');
  }

  /* 계층 접기 — 어느 행이 자식을 갖는지는 '다음 행의 단이 더 깊은가' 로
     정해집니다. 구획(SUMMARY / DETAILS)을 넘어가면 자식이 아닙니다. */
  function wideTree(rows) {
    var kids = [], parent = [], i, j;
    for (i = 0; i < rows.length; i++) {
      kids.push(i + 1 < rows.length &&
                rows[i + 1].lv > rows[i].lv &&
                rows[i + 1].sec === rows[i].sec);
      parent.push(-1);
      for (j = i - 1; j >= 0; j--) {
        if (rows[j].sec !== rows[i].sec) break;
        if (rows[j].lv < rows[i].lv) { parent[i] = j; break; }
      }
    }
    return { kids: kids, parent: parent };
  }

  function wideVisible(rows, tree, open) {
    var vis = [];
    for (var i = 0; i < rows.length; i++) {
      var p = tree.parent[i], ok = true;
      while (p >= 0) {
        if (!open[p]) { ok = false; break; }
        p = tree.parent[p];
      }
      if (ok) vis.push(i);
    }
    return vis;
  }

  function renderWide(D, opt, onToggle) {
    var cols = wideCols(D, opt);
    var rows = D.rows;
    var tree = wideTree(rows);
    var vis = wideVisible(rows, tree, opt.open);
    var table = el('table', 'wide');
    var i, j, tr;

    /* 머리 4줄 — 수량|금액 / MTD|YTD / 기간·채널 / 값·shr.
       위 세 줄은 같은 값이 이어지는 만큼 묶습니다. */
    var thead = el('thead');
    var levels = [
      function (c) { return c.m; },
      function (c) { return c.m + '|' + c.per; },
      function (c) { return c.m + '|' + c.per + '|' + c.g3; }
    ];
    var labels = [
      function (c) { return c.m; },
      function (c) { return c.per; },
      function (c) { return c.g3; }
    ];
    for (var lv = 0; lv < 3; lv++) {
      tr = el('tr', 'h' + (lv + 1));
      tr.appendChild(el('th', 'metric', lv === 2 ? '품목' : ''));
      i = 0;
      while (i < cols.length) {
        j = i;
        while (j < cols.length && levels[lv](cols[j]) === levels[lv](cols[i])) j++;
        var th = el('th', 'grp ' + (cols[i].cls || ''));
        th.colSpan = j - i;
        /* 수량/금액·MTD/YTD 는 100열이 넘게 이어집니다. 칸 가운데에 두면
           가로로 밀었을 때 라벨이 화면 밖으로 나가 '지금 어느 블록인가' 를
           알 수 없습니다 — 라벨만 왼쪽에 붙여 둡니다. */
        th.appendChild(el('span', lv < 2 ? 'stick' : '', labels[lv](cols[i])));
        tr.appendChild(th);
        i = j;
      }
      thead.appendChild(tr);
    }
    tr = el('tr', 'h4');
    tr.appendChild(el('th', 'metric', ''));
    for (i = 0; i < cols.length; i++) {
      var c = cols[i];
      tr.appendChild(el('th', 'sub ' + (c.cls || ''),
                        c.t === 'g' ? '증감' : (c.t === 's' ? 'shr' : '값')));
    }
    thead.appendChild(tr);
    table.appendChild(thead);

    var tbody = el('tbody');
    for (var vi = 0; vi < vis.length; vi++) {
      var r = vis[vi], row = rows[r];
      tr = el('tr', 'lv' + row.lv + (row.total ? ' is-total' : '') +
                    (row.sec === 'det' ? ' is-det' : ''));
      var cell = el('th', 'metric');
      cell.scope = 'row';
      cell.style.paddingLeft = (10 + row.lv * 14) + 'px';
      if (tree.kids[r]) {
        (function (idx) {
          var btn = el('button', 'tw', opt.open[idx] ? '▾' : '▸');
          btn.type = 'button';
          btn.setAttribute('aria-expanded', opt.open[idx] ? 'true' : 'false');
          btn.setAttribute('aria-label',
                           rows[idx].name + (opt.open[idx] ? ' 접기' : ' 펼치기'));
          btn.onclick = function () { onToggle(idx); };
          cell.appendChild(btn);
        })(r);
      } else {
        cell.appendChild(el('span', 'tw-none', ''));
      }
      var nm = el('span', 'nm', row.name);
      if (row.code) nm.title = row.code;
      cell.appendChild(nm);
      tr.appendChild(cell);

      for (i = 0; i < cols.length; i++) {
        var col = cols[i];
        var raw = wideRaw(D, col, r);
        var cls = 'num ' + (col.cls || '') + (col.t === 's' ? ' shr' : '');
        if (col.t === 'g') cls += ' ' + dirClass(raw);
        if (raw === null || raw === 0) cls += ' nil';
        tr.appendChild(el('td', cls, wideText(D, col, r)));
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    return table;
  }

  function wideCsv(D, opt) {
    var cols = wideCols(D, opt);
    var rows = D.rows;
    var tree = wideTree(rows);
    var vis = wideVisible(rows, tree, opt.open);
    var out = [], i, line;

    var heads = [
      ['', function (c) { return c.m; }],
      ['', function (c) { return c.per; }],
      ['품목', function (c) { return c.g3; }],
      ['', function (c) { return c.t === 'g' ? '증감' : (c.t === 's' ? 'shr' : '값'); }]
    ];
    for (var h = 0; h < heads.length; h++) {
      line = [csvCell(heads[h][0])];
      for (i = 0; i < cols.length; i++) line.push(csvCell(heads[h][1](cols[i])));
      out.push(line.join(','));
    }
    for (var vi = 0; vi < vis.length; vi++) {
      var r = vis[vi];
      var indent = new Array(rows[r].lv + 1).join('  ');
      line = [csvCell(indent + rows[r].name)];
      for (i = 0; i < cols.length; i++) {
        var v = wideRaw(D, cols[i], r);
        line.push(v === null ? '' : String(v));
      }
      out.push(line.join(','));
    }
    return out.join('\r\n');
  }

  return {
    fmt: fmt, fmtDelta: fmtDelta, fmtGrowth: fmtGrowth, dirClass: dirClass,
    renderMatrix: renderMatrix, renderCross: renderCross,
    heatLegend: heatLegend, crossCsv: crossCsv, toCsv: toCsv, download: download,
    readState: readState, writeState: writeState, el: el, comma: comma,
    renderWide: renderWide, wideCsv: wideCsv, wideTree: wideTree
  };
})();
