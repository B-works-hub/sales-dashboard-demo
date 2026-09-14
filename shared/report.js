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

  return {
    fmt: fmt, fmtDelta: fmtDelta, fmtGrowth: fmtGrowth, dirClass: dirClass,
    renderMatrix: renderMatrix, toCsv: toCsv, download: download,
    readState: readState, writeState: writeState, el: el, comma: comma
  };
})();
