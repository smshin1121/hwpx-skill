#!/usr/bin/env python3
"""fill_hwpx.py 스모크 테스트 — analyze/fill/replace/add-row/add-para/verify 전체 파이프라인.

사용법: python3 tests/test_fill_hwpx.py
종료 코드 0이면 전체 통과.
"""
import json
import subprocess
import sys
import tempfile
import zipfile
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILL = ROOT / "scripts" / "fill_hwpx.py"
BUILD = Path(__file__).resolve().parent / "build_test_form.py"

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")


def run(*args, expect=0):
    r = subprocess.run([sys.executable, str(FILL), *map(str, args)],
                       capture_output=True, text=True)
    if r.returncode != expect:
        print(f"    [exit {r.returncode}] {r.stderr.strip()[:200]}")
    out = None
    if r.stdout.strip():
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError:
            pass
    return r.returncode, out


def main():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        form = d / "form.hwpx"
        subprocess.run([sys.executable, str(BUILD), str(form)],
                       check=True, capture_output=True)

        # ─ analyze ─
        code, rep = run("analyze", form)
        check("analyze 실행", code == 0)
        check("analyze 타겟 발견", rep and rep["target_count"] >= 9,
              f"(got {rep and rep['target_count']})")

        # ─ fill (라벨/체크박스/괄호/어노테이션/헤더행/인라인) ─
        values = {"성명": "홍길동", "연락처": "010-1234-5678",
                  "주소": "서울특별시 강남구", "한자": "洪吉童", "동의": "☑",
                  "일반통": "3", "품명": "노트북", "수량": "2", "작성자": "김철수"}
        vf = d / "values.json"
        vf.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        out1 = d / "out1.hwpx"
        code, rep = run("fill", form, out1, "--values", vf)
        check("fill 성공", code == 0 and rep["ok"])
        check("fill 9개 채움", rep and len(rep["filled"]) == 9,
              f"(got {rep and len(rep['filled'])})")
        check("fill unmatched 없음", rep and not rep["unmatched"])

        xml = zipfile.ZipFile(out1).read("Contents/section0.xml").decode()
        check("self-closing run에 charPr 유지 삽입",
              '<hp:run charPrIDRef="2"><hp:t>홍길동</hp:t></hp:run>' in xml)
        check("어노테이션 보존", "서울특별시 강남구 (한자：洪吉童)" in xml)
        check("체크박스", "☑동의 □비동의" in xml)
        check("괄호 빈칸", "일반(3)통" in xml)

        # ─ replace (run 경계를 넘는 문구) ─
        mf = d / "map.json"
        mf.write_text(json.dumps({"2025년 기준으로": "2026년 6월 기준으로"},
                                 ensure_ascii=False), encoding="utf-8")
        out2 = d / "out2.hwpx"
        code, rep = run("replace", out1, out2, "--map", mf)
        check("replace 성공 (run 경계)", code == 0 and rep["total"] == 1)

        # ─ add-row ─
        rf = d / "rows.json"
        rf.write_text('[["모니터","5"],["키보드","10"]]', encoding="utf-8")
        out3 = d / "out3.hwpx"
        code, rep = run("add-row", out2, out3, "--table", 1, "--rows", rf)
        check("add-row 성공", code == 0 and rep["ok"])
        xml = zipfile.ZipFile(out3).read("Contents/section0.xml").decode()
        m = re.search(r'<hp:tbl id="9200"[^>]*rowCnt="(\d+)"', xml)
        check("add-row rowCnt 갱신", m and m.group(1) == "4")
        ids = re.findall(r'<hp:p id="(\d+)"', xml)
        check("add-row 문단 id 고유", len(ids) == len(set(ids)))

        # add-row 셀 수 불일치 거부
        bf = d / "bad.json"
        bf.write_text('[["하나"]]', encoding="utf-8")
        code, _ = run("add-row", out3, d / "x.hwpx", "--table", 1,
                      "--rows", bf, expect=1)
        check("add-row 셀 수 불일치 거부", code == 1)

        # ─ add-para ─
        out4 = d / "out4.hwpx"
        code, rep = run("add-para", out3, out4, "--after", "작성자",
                        "--text", "자동 생성 문단입니다.")
        check("add-para 성공", code == 0 and rep["ok"])

        # ─ fill --cells (좌표 지정) ─
        cf = d / "cells.json"
        cf.write_text('[{"table":0,"row":1,"col":1,"value":"010-9999-8888"}]',
                      encoding="utf-8")
        out5 = d / "out5.hwpx"
        code, rep = run("fill", out4, out5, "--cells", cf)
        check("fill --cells 성공", code == 0 and rep["ok"])

        # ─ verify (값 존재 + 원본 보존) ─
        av = d / "all.json"
        av.write_text(json.dumps({
            "v1": "2026년 6월 기준으로", "v2": "모니터", "v3": "키보드",
            "v4": "010-9999-8888", "v5": "자동 생성 문단입니다.",
            "성명": "홍길동"}, ensure_ascii=False), encoding="utf-8")
        code, rep = run("verify", out5, "--values", av, "--original", form)
        check("verify 전체 통과", code == 0 and rep["ok"])
        check("섹션 외 엔트리 바이트 보존",
              rep and rep["changed_entries"] == ["Contents/section0.xml"])

        # ─ 무매칭 → 원본 바이트 동일 ─
        nf = d / "nomatch.json"
        nf.write_text('{"존재하지않는라벨":"값"}', encoding="utf-8")
        out6 = d / "out6.hwpx"
        code, _ = run("fill", form, out6, "--values", nf, expect=2)
        check("무매칭 시 exit 2", code == 2)
        check("무매칭 시 원본 바이트 동일",
              form.read_bytes() == out6.read_bytes())

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
