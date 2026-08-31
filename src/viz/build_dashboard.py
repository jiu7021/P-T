"""Module D. 단일 HTML 대시보드 생성.

    .venv/bin/python src/viz/build_dashboard.py

데이터를 인라인으로 넣어 외부 API 호출이 없는 파일 하나를 만든다.
브라우저 저장소(localStorage 등)를 쓰지 않는다.

출력: output/dashboard.html
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIZ = ROOT / "src" / "viz"
DATA = ROOT / "data" / "processed" / "dashboard_data.json"
OUT = ROOT / "output" / "dashboard.html"
# GitHub Pages는 저장소 루트(또는 /docs)의 index.html을 서빙한다.
# 같은 파일을 루트에도 둬서 https://<user>.github.io/<repo>/ 로 바로 열리게 한다.
PAGES = ROOT / "index.html"
# GitHub Pages 소스를 /docs 로 둘 경우 서빙되는 경로. 소개 페이지(docs/index.html)에서
# "분석 워크벤치 열기"로 이 파일을 연다.
DOCS_PAGE = ROOT / "docs" / "workbench.html"


def main() -> int:
    for p in (VIZ / "dashboard_template.html", VIZ / "dashboard.js", DATA):
        if not p.exists():
            print(f"없음: {p}", file=sys.stderr)
            return 1

    html = (VIZ / "dashboard_template.html").read_text(encoding="utf-8")
    js = (VIZ / "dashboard.js").read_text(encoding="utf-8")
    data = DATA.read_text(encoding="utf-8")

    # </script> 가 JSON 문자열 안에 있으면 파서가 조기 종료한다.
    data = data.replace("</script>", "<\\/script>")

    html = html.replace("__DATA__", data).replace("__SCRIPT__", js)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    PAGES.write_text(html, encoding="utf-8")
    DOCS_PAGE.parent.mkdir(exist_ok=True)
    DOCS_PAGE.write_text(html, encoding="utf-8")
    print(f"저장: {OUT.relative_to(ROOT)}  {OUT.stat().st_size:,} B "
          f"({OUT.stat().st_size/1e6:.2f} MB)")
    print(f"저장: {PAGES.name}  (루트 Pages용 사본)")
    print(f"저장: docs/{DOCS_PAGE.name}  (docs Pages용 사본)")
    print("외부 CDN·API 없음, 브라우저 저장소 미사용, 다크모드 대응")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
