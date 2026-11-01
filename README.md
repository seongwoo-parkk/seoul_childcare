# 아이 키우기 좋은 동네는 어디인가

서울 424개 행정동의 어린이집 공급을 **밀도 · 다양성 · 형평성** 지표로 측정하고 지도와 그래프로 해석한 웹앱입니다.
스마트시티융합기술세미나(스마트도시데이터분석) 과제 3 「도시 현상을 지표로 측정하고 공간적으로 해석하기」

- 앱: https://seoul-childcare.prime-checker.workers.dev
- 코드: https://github.com/seongwoo-parkk/seoul_childcare

## 연구 질문
1. 서울 행정동별로 영유아 인구 대비 어린이집 정원(공급률)은 어떻게 다른가?
2. 아이가 많이 사는 동네일수록 어린이집 공급은 충분한가, 부족한가?
3. 공급은 행정동 사이에 얼마나 불평등하며(Gini), 운영 유형의 구성(다양성·공공성)은 동네마다 어떻게 다른가?

## 지표 (공간 단위: 행정동 424개)
| 지표 | 계산식 | 의미 |
| --- | --- | --- |
| 공급률 (밀도) | 정원 ÷ 0~9세 인구 × 1,000 | 아이 1,000명당 어린이집 자리 |
| 운영 유형 다양성 (Gini–Simpson) | 1 − Σ p_k² (p_k: 7개 운영 유형별 정원 비중) | 0 = 한 유형만, 최대 0.857 |
| 형평성 (Gini) | 공급률 순 정렬 후 누적 아동·정원 비율의 로렌츠 곡선 | 0 = 완전 균등 |
| 국공립 정원 LQ | (동 국공립 비중) ÷ (서울 국공립 비중) | 1보다 크면 국공립 비중이 서울보다 높음 |

보조: 정원 충족률(현원 ÷ 정원), 직장어린이집 제외 공급률, 아동 LQ(교차 분류용)

## 주요 결과
- 서울 평균 공급률은 0~9세 1,000명당 274.9명, 행정동 간 Gini는 0.285
- 아동 수와 공급률의 스피어만 순위상관은 −0.50: 아동이 2배인 동의 정원은 약 1.48배에 그침
- 아동 비중이 높으면서 공급률이 평균보다 낮은 109개 동에 서울 0~9세의 44.4%가 거주(강남·양천·송파·서초에 집중)
- 도심(중구·종로)의 높은 공급률은 직장어린이집 영향이지만, 이를 빼도 Gini는 0.281

## 자료
- 서울 열린데이터광장 OpenAPI: 서울시 어린이집 정보(`ChildCareInfo`, 2026-11-01), 서울 생활인구 행정동(`SPOP_LOCAL_RESD_DONG`, 2026년 7월 03시대 평균)
- 행정동 경계: [vuski/admdongkor](https://github.com/vuski/admdongkor) ver20250101

## 재현
```
python scripts/fetch_data.py        # 원자료 수집 → cache/ (API 키는 ~/.env 의 SEOUL_API_KEY에서 읽음)
python scripts/build_indicators.py  # 지표 계산 → data/
```
필요 패키지: pandas, numpy, geopandas, shapely. API 키는 저장소에 포함하지 않습니다.

## 파일
- `index.html`, `app.js`: 웹앱 (Leaflet 지도, Plotly 그래프)
- `data/dong.geojson`: 행정동 경계와 지표, `data/dong_indicators.csv`: 지표 표, `data/summary.json`, `data/gu.json`: 요약
- `scripts/`: 수집·계산 코드
