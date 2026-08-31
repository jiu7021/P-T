"""GitHub Pages용 워크벤치 생성 — SnowUI 셸 + 기존 분석 화면.

    .venv/bin/python src/viz/build_pages.py

만드는 것: docs/index.html (Pages 소스가 /docs 이므로 이 파일이 첫 화면이다)

설계
    분석 로직(src/viz/dashboard.js)은 그대로 재사용한다. 화면이 참조하는 요소 id를
    유지했기 때문에 로직을 다시 쓸 필요가 없다. 바뀐 것은 껍데기뿐이다.
      - 탭 전환 → 사이드바 레일 + 스크롤 섹션
      - 자체 스타일 → SnowUI 토큰 (snowui-shell.css + workbench-extra.css)

    키트 파일(snowui-shell.css / .js)은 수정하지 않는다. 기존 코드가 만드는
    요소들의 스타일은 workbench-extra.css 에서 키트 토큰만 써서 정의한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIZ = ROOT / "src" / "viz"
DOCS = ROOT / "docs"
DATA = ROOT / "data" / "processed" / "dashboard_data.json"
OUT = DOCS / "index.html"

# 레일 항목 ↔ 섹션. 순서가 곧 화면 순서다.
# (섹션 id, 레일 표기, 원본 템플릿의 탭 id, 레일 그룹)
SECTIONS = [
    ("s-overview", "한눈에 보기", None, "개요"),
    # 눌러볼 수 있는 화면을 앞에 둔다. 처음 여는 사람이 바로 만져볼 수 있어야 한다.
    ("s-eds", "EDS 웨이퍼 테스트", "tE", "직접 판정해보기"),
    ("s-fa", "FA · SEM 결함 분석", "t2", "직접 판정해보기"),
    ("s-map", "웨이퍼 맵 패턴", "t1", "직접 판정해보기"),
    # 배경이 되는 공정 데이터 분석은 뒤로 뺀다.
    ("s-sensor", "공정 센서 관리도", "tS", "공정 데이터 분석"),
    ("s-feedback", "판정 피드백", "t4", "기록"),
    ("s-limit", "한계와 근거", "t5", "기록"),
]


def extract_sections(tpl: str) -> dict[str, str]:
    """원본 템플릿에서 각 탭의 내부 마크업을 꺼낸다."""
    out = {}
    for m in re.finditer(r'<section id="(t[E1-5S])" class="tab[^"]*">(.*?)</section>',
                         tpl, re.S):
        out[m.group(1)] = m.group(2)
    return out


def adapt(html: str) -> str:
    """기존 마크업을 SnowUI 셸 안에서 쓸 수 있게 다듬는다.

    - class="panel"  → class="card"   (SnowUI 의 .panel 은 섹션 단위라 의미가 다르다)
    - class="scroll" → class="xscroll" (SnowUI 의 .scroll 은 페이지 스크롤 컨테이너다)
    - <h3> → <h4>                      (섹션 제목이 h2 이므로 한 단계 내린다)
    """
    html = html.replace('class="panel"', 'class="card"')
    html = html.replace('class="scroll"', 'class="xscroll"')
    html = re.sub(r'<(/?)h3(\s|>)', r'<\1h4\2', html)
    return html


def rail(sections) -> str:
    parts, cur = [], None
    for sid, label, _, group in sections:
        if group != cur:
            if cur is not None:
                parts.append("  </nav>")
            parts.append(f'  <div class="rail-sec">{group}</div>')
            parts.append('  <nav class="rail-group">')
            cur = group
        parts.append(f'    <a class="rail-row" href="#{sid}">'
                     f'<span class="ri"></span>{label}</a>')
    parts.append("  </nav>")
    return "\n".join(parts)


OVERVIEW = """
      <section class="panel" id="s-overview">
        <div class="panel-head"><h2>한눈에 보기</h2>
          <div class="hint">공개 데이터 3종 · 칩 213만 개 전수 판정</div></div>
        <div class="chips">
          <span class="chip real">웨이퍼 맵 · 공정 센서 · 결함 이미지 = 실측 데이터</span>
          <span class="chip syn">검사별 측정값 · 칩 내부 고장 주소 = 가정으로 채움</span>
          <span class="chip look">원인 공정 = 문헌 조회 (모델 아님)</span>
        </div>
        <div class="kpi-row">
          <div class="kpi tint">
            <div class="kpi-lab">전수 판정한 칩</div>
            <div class="kpi-val">2,128,718</div>
            <div class="kpi-sub">웨이퍼 2,000장 · 실측 기반</div></div>
          <div class="kpi tint-2">
            <div class="kpi-lab">불량 중 복구 가능</div>
            <div class="kpi-val">53.6 %</div>
            <div class="kpi-sub">불량 칩 490,546개 기준</div></div>
          <div class="kpi">
            <div class="kpi-lab">검증이 잡아낸 오류</div>
            <div class="kpi-val">275,159</div>
            <div class="kpi-sub">정상 칩이 불량으로 뒤집힌 건수</div></div>
          <div class="kpi">
            <div class="kpi-lab">엄격 검증 후 p 값</div>
            <div class="kpi-val">0.010 → 0.155</div>
            <div class="kpi-sub">시간 순으로 나누자 사라진 유의성</div></div>
        </div>
        <p class="para">반도체 칩은 둥근 원판(웨이퍼) 위에 수백 개가 한꺼번에 만들어집니다.
          다 만든 뒤 <b>웨이퍼 테스트</b>라는 전기 검사를 거치는데, 바늘을 칩에 대고 전압을 넣어
          정해진 출력이 나오는지 봅니다. 여기서 떨어진 칩은 버리거나, 미리 넣어둔
          <b>여분 배선</b>으로 고쳐 씁니다. 아래 화면들은 그 판정과 원인 추적의 흐름을
          공개 데이터로 재현한 것입니다.</p>
        <p class="para">왼쪽 차례대로 보시면 됩니다. 먼저 <b>칩 하나하나를 판정</b>하는 화면에서
          웨이퍼 위의 칩을 눌러보시고, 걸러진 칩을 <b>사진으로 확인</b>한 뒤,
          웨이퍼 전체에 나타나는 <b>불량의 모양</b>을 봅니다. 마지막으로 그 배경이 되는
          <b>공정 센서 기록</b>이 이어집니다. 각 화면에서 실측으로 정한 부분과 가정으로 채운
          부분을 구분해 표시했습니다.</p>
        <div class="turn">
          <b>이 워크벤치가 보여주려는 것은 판정 결과가 아니라 판정의 근거입니다.</b>
          <p>칩을 누르면 어떤 검사에서 어떤 값이 나와 그 등급이 됐는지, 여분 배선이 어디에
            배정됐고 무엇이 덮이지 않았는지가 함께 나옵니다. 검증에서 무너진 결과도
            지우지 않고 그대로 남겼습니다.</p>
        </div>
      </section>
"""


def main() -> int:
    tpl_path = VIZ / "dashboard_template.html"
    js_path = VIZ / "dashboard.js"
    for p in (tpl_path, js_path, DATA, DOCS / "snowui-shell.css",
              DOCS / "snowui-shell.js", DOCS / "workbench-extra.css"):
        if not p.exists():
            print(f"없음: {p}", file=sys.stderr)
            return 1

    tpl = tpl_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")
    data = DATA.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
    src = extract_sections(tpl)
    missing = [t for _, _, t, _ in SECTIONS if t and t not in src]
    if missing:
        print(f"원본 템플릿에서 못 찾은 탭: {missing}", file=sys.stderr)
        return 1

    body = [OVERVIEW]
    for sid, label, tab, _ in SECTIONS:
        if tab is None:
            continue
        inner = adapt(src[tab])
        body.append(f'      <section class="panel" id="{sid}">\n'
                    f'        <div class="panel-head"><h2>{label}</h2></div>\n'
                    f'{inner}\n      </section>\n')

    # 탭 전환 로직 제거 — 레일과 스크롤이 그 역할을 한다
    js = re.sub(r"document\.querySelectorAll\('nav button'\)\.forEach\(b => b\.onclick.*?\}\);\n",
                "// 탭 전환은 SnowUI 레일이 담당한다(snowui-shell.js).\n", js, flags=re.S)
    # 요소가 없으면 조용히 넘어가도록 한다. 화면 구성이 바뀌어도 나머지가 멈추지 않는다.
    # 등급 색은 두 용도로 쓰인다.
    #   막대 배경·캔버스 채우기 → 면이므로 원색 그대로 둔다(테마 무관하게 구분된다)
    #   글자 색               → 배경 대비가 필요하다. 테마별로 달라야 하므로 CSS 변수로 뺀다
    js = js.replace(
        "const G_COL = ['#4ca85c', '#f0bf33', '#d93630'];",
        "const G_COL = ['#4ca85c', '#f0bf33', '#d93630'];          // 면(막대·캔버스)용\n"
        "const G_TXT = ['var(--grade-good)', 'var(--grade-rep)', 'var(--grade-fail)'];  // 글자용")
    js = js.replace('<b style="color:${G_COL[i]}">', '<b style="color:${G_TXT[i]}">')
    js = js.replace('color:${G_COL[gi]};margin-bottom', 'color:${G_TXT[gi]};margin-bottom')
    js = js.replace("const $ = (id) => document.getElementById(id);",
                    "const $ = (id) => document.getElementById(id) "
                    "|| document.createElement('div');  // 없는 요소는 빈 노드로 대체")

    html = f"""<!doctype html>
<html lang="ko" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>웨이퍼 테스트 판정 워크벤치</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="snowui-shell.css">
<link rel="stylesheet" href="workbench-extra.css">
</head>
<body>
<div class="shell">

<aside class="rail">
  <div class="rail-brand"><span class="rail-dot"></span><span>웨이퍼 테스트 워크벤치</span></div>

{rail(SECTIONS)}

  <nav class="rail-group rail-ext">
    <a class="rail-row" href="story.html">프로젝트 설명 ↗</a>
    <a class="rail-row" href="https://github.com/jiu7021/P-T">저장소 ↗</a>
    <a class="rail-row" href="http://mirlab.org/dataset/public/">WM-811K 데이터 ↗</a>
    <a class="rail-row" href="https://doi.org/10.5281/zenodo.16895427">Carinthia-S 데이터 ↗</a>
    <a class="rail-row" href="https://archive.ics.uci.edu/dataset/179/secom">SECOM 데이터 ↗</a>
  </nav>

  <div class="rail-foot">SnowUI Design System</div>
</aside>

<div class="col">
  <header class="topbar">
    <div class="crumb"><span>포트폴리오</span><span class="sep">/</span><b id="crumb-cur">한눈에 보기</b></div>
    <div class="topbar-r">
      <span class="badge">개인 프로젝트 · 2026.08</span>
      <button id="theme-btn" class="icon-btn" type="button" aria-label="테마 전환">◐</button>
    </div>
  </header>

  <div class="scroll">
    <div class="hero">
      <h1>웨이퍼 테스트 판정 및 불량 분석 워크벤치</h1>
      <p class="sub">공정 센서가 흔들린 시점을 찾고, 칩 213만 개를 판정하고,
        걸러진 칩의 원인을 좁히는 흐름을 공개 데이터만으로 구현했습니다.
        판정 결과보다 <b>판정의 근거를 눈에 보이게 만드는 것</b>을 목표로 삼았습니다.</p>
    </div>

    <main>
{''.join(body)}
    </main>

    <footer class="ftr">
      데이터 출처 · WM-811K (MIR Lab, National Taiwan University) — M.-J. Wu, J.-S. R. Jang, J.-L. Chen,
      IEEE Trans. Semicond. Manuf., 28(1), 2015 · Carinthia-S (Zenodo, CC BY 4.0, doi:10.5281/zenodo.16895427) ·
      SECOM (UCI Machine Learning Repository) · 검사 규격은 DDR4 공개 데이터시트 참조.
      칩 내부 고장 주소와 검사별 측정값은 공개 자료가 없어 가정으로 채운 값입니다.
      <div id="gen" style="margin-top:6px"></div>
    </footer>
  </div>
</div>
</div>

<script id="payload" type="application/json">{data}</script>
<script src="snowui-shell.js"></script>
<script>
/* 레일 클릭 폴백 — 키트 파일은 수정하지 않는다.
   키트는 scrollTo({{behavior:'smooth'}}) 로 이동하는데, 부드러운 스크롤이 듣지 않는
   환경이 있다(프레임이 돌지 않는 자동화 브라우저 등). 그 경우 레일을 눌러도
   화면이 그대로 있어 아무 반응이 없어 보인다. 키트 핸들러가 돈 뒤 위치를 확인하고,
   움직이지 않았으면 즉시 이동시킨다. 정상 환경에서는 아무 일도 하지 않는다. */
(function () {{
  var sc = document.querySelector('.scroll');
  if (!sc) return;
  document.querySelectorAll('.rail-row[href^="#"]').forEach(function (a) {{
    a.addEventListener('click', function () {{
      var el = document.querySelector(a.getAttribute('href'));
      if (!el) return;
      var want = el.offsetTop - 12;
      setTimeout(function () {{
        if (Math.abs(sc.scrollTop - want) > 40) {{
          sc.scrollTop = want;
          // 위치를 직접 대입하면 scroll 이벤트가 안 오는 환경이 있다.
          // 그러면 레일 표시와 상단 제목이 갱신되지 않으므로 직접 알린다.
          sc.dispatchEvent(new Event('scroll'));
        }}
      }}, 450);
    }});
  }});
}})();
</script>
<script>
{js}
</script>
</body>
</html>
"""
    OUT.write_text(html, encoding="utf-8")
    print(f"저장: docs/{OUT.name}  {OUT.stat().st_size:,} B "
          f"({OUT.stat().st_size/1e6:.2f} MB)")
    print(f"섹션 {len(SECTIONS)}개 · 외부 CDN 은 웹폰트만 · 브라우저 저장소 미사용")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
