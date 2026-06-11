# HWPX 트러블슈팅

## "한글에서 빈 페이지로 열림"

| 원인 | 해결 |
|------|------|
| fix_namespaces.py 미실행 | 반드시 후처리 실행 |
| section0.xml에 secPr 없음 | 첫 문단 첫 run에 secPr + colPr 포함 |
| charPrIDRef가 header.xml에 없는 ID 참조 | 템플릿에 정의된 ID만 사용 |
| mimetype이 첫 ZIP 엔트리 아님 | build_hwpx.py 사용 시 자동 처리 |

## ★ "한컴이 '손상된 문서' 복구 대화상자를 띄움" (secPr 불완전)

> **validate.py(XML 유효성)와 fill verify(값 존재)를 통과해도 한컴이 안 열리는 가장 흔한 원인.**
> LLM이 section0.xml을 손수 작성하면 secPr을 `<hp:secPr pageWidth=".." leftMargin="..">`처럼
> **가짜 속성**으로 만들기 쉽다. 실제 HWPX 스키마는 secPr의 **자식 요소**
> `<hp:pagePr>`(용지 크기)+`<hp:margin>`(여백)을 요구한다. 이게 없으면 한컴은
> 문서를 그릴 수 없어 손상 판정한다.

| 증상 | 진단 | 해결 |
|------|------|------|
| validate 통과·한컴 손상 경고 | `fill_hwpx.py check 파일.hwpx` 실행 → secPr errors 확인 | 정상 HWPX의 secPr을 이식 |
| secPr에 pageWidth/leftMargin 등 속성 | LLM이 손수 작성한 가짜 secPr | 동일 용지의 정상 파일에서 `<hp:secPr>...</hp:secPr>` 통째 복사 |
| secPr에 pagePr/margin 자식 없음 | 필수 자식 누락 | templates/base 또는 정상 파일의 secPr 사용 |

```bash
# 배포 전 항상 열림 가능성 점검 (값 없이도 실행 가능)
python3 scripts/fill_hwpx.py check output.hwpx     # exit 0=정상, 2=secPr 문제
```

> **교훈: LLM이 section0.xml을 처음부터 쓰지 말 것.** 정상 HWPX(워크플로우 H 변환본
> 또는 한컴 저장본)를 베이스로 fill/replace만 적용하면 secPr이 자동 보존된다.

## "내용은 있지만 서식이 깨짐"

| 원인 | 해결 |
|------|------|
| 템플릿과 section0.xml의 스타일 ID 불일치 | analyze_template.py로 실제 ID 확인 |
| header.xml의 itemCnt 불일치 | charPr/paraPr/borderFill 수와 맞추기 |
| 글꼴 미설치 | 함초롬돋움, 함초롬바탕 등 필요 |

## "표가 잘려서 보임"

| 원인 | 해결 |
|------|------|
| 열 너비 합 ≠ 본문폭 | 열 너비의 합을 본문폭과 일치 |
| rowCnt/colCnt 불일치 | 실제 행/열 수와 속성값 맞추기 |

## "이미지 포함 문서에서 한컴오피스 크래시"

| 원인 | 해결 |
|------|------|
| `<hp:pic>`에 필수 자식 요소 누락 | xml-structure.md의 `<hp:pic>` 전체 구조 사용 |
| `href=""`, `groupLevel="0"`, `instid`, `reverse="0"` 누락 | `<hp:pic>` 속성에 반드시 포함 |
| `<hp:renderingInfo>` 미포함 | transMatrix, scaMatrix, rotMatrix 전부 포함 |
| `<hp:imgClip>`, `<hp:imgDim>`, `<hp:effects/>` 누락 | 전부 포함 |
| `<hp:sz>`, `<hp:pos>` 순서 잘못 | `<hp:effects/>` 뒤에 배치 |
| `</hp:pic>` 뒤 `<hp:t/>` 누락 | run 안에 빈 텍스트 노드 추가 |
| content.hpf에 이미지 미등록 | `<opf:item>` 추가 (isEmbeded="1") |

## "python-hwpx 에러"

| 원인 | 해결 |
|------|------|
| HwpxDocument.open() 실패 | XML-first 접근 또는 ZIP-level 치환 사용 |
| ObjectFinder 에러 | `pip install python-hwpx --break-system-packages` |

## Hancom says the file is damaged after text replacement

| Cause | Fix |
|------|-----|
| Stale `hp:linesegarray` layout caches remain after editing text outside Hancom | Run `python3 scripts/finalize_hwpx.py output.hwpx --strip-linesegarray` before validation |
| XML validation passed but Hancom still refuses the file | Run `python3 scripts/validate.py output.hwpx --hancom` on Windows with Hancom Office installed |
| Template was filled by rewriting XML nodes and losing run/control structure | Recreate from the original template with `clone_form.py` or ZIP-level string replacement, then finalize |

## Text is squeezed or overlaps in table cells

| Cause | Fix |
|------|-----|
| Long content is stored as one paragraph in a fixed-height cell | Split it into real `hp:p` paragraphs or list items |
| Row height was not updated after content expansion | Increase every `hp:cellSz/@height` in the row and update table `hp:sz/@height` |
| Text was forced to fit by changing the template structure | Keep the template structure; write an editing note when content cannot fit without a format decision |

Use:

```bash
python3 scripts/finalize_hwpx.py output.hwpx --layout
```

The layout check is warning-based. It identifies likely risks that still need
template-aware review.
