"""원자료 수집: 서울시 어린이집 정보, 행정동 생활인구(2026년 7월 03시), 행정동 경계.

API 키는 사용자 홈의 .env(SEOUL_API_KEY)에서만 읽고 어디에도 저장하지 않는다.
결과는 cache/ 에 저장한다 (저장소에는 올리지 않음).
"""
import os, re, json, time, calendar, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'cache')
os.makedirs(CACHE, exist_ok=True)

env = open(os.path.join(os.path.expanduser('~'), '.env'), encoding='utf-8').read()
KEY = re.search(r'SEOUL_API_KEY\s*=\s*"?([^"\r\n]+)"?', env).group(1).strip()
BOUNDARY_URL = 'https://raw.githubusercontent.com/vuski/admdongkor/master/ver20250101/HangJeongDong_ver20250101.geojson'


def api(path, tries=4):
    url = f'http://openapi.seoul.go.kr:8088/{KEY}/json/{path}'
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except Exception as e:
            if k == tries - 1:
                raise RuntimeError(f'{path.split("/")[0]} 요청 실패: {type(e).__name__}')
            time.sleep(2 + 3 * k)


def fetch_childcare():
    first = api('ChildCareInfo/1/1/')['ChildCareInfo']
    total = first['list_total_count']
    rows = []
    for s in range(1, total + 1, 1000):
        e = min(s + 999, total)
        rows += api(f'ChildCareInfo/{s}/{e}/')['ChildCareInfo']['row']
        time.sleep(0.3)
    # 연락처·홈페이지 등 분석에 필요 없는 항목은 저장하지 않는다
    keep = ['STCODE', 'CRNAME', 'SIGUNNAME', 'CRTYPENAME', 'CRSTATUSNAME', 'CRADDR', 'CRCAPAT', 'CRCHCNT',
            'LA', 'LO', 'DATASTDRDT']
    rows = [{k: r.get(k) for k in keep} for r in rows]
    json.dump(rows, open(os.path.join(CACHE, 'childcare.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('childcare', total, len(rows))


def fetch_spop(year=2026, month=7, hour='03'):
    days = calendar.monthrange(year, month)[1]
    out = {}
    for d in range(1, days + 1):
        dt = f'{year}{month:02d}{d:02d}'
        res = api(f'SPOP_LOCAL_RESD_DONG/1/1000/{dt}/{hour}')
        body = res.get('SPOP_LOCAL_RESD_DONG')
        if not body:
            continue
        out[dt] = body['row']
        time.sleep(0.3)
    json.dump(out, open(os.path.join(CACHE, f'spop_{year}{month:02d}_{hour}.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('spop days', len(out), 'rows/day', sorted({len(v) for v in out.values()}))


def fetch_boundary():
    p = os.path.join(CACHE, 'HangJeongDong_ver20250101.geojson')
    if not os.path.exists(p):
        with urllib.request.urlopen(BOUNDARY_URL, timeout=300) as r:
            open(p, 'wb').write(r.read())
    print('boundary bytes', os.path.getsize(p))


if __name__ == '__main__':
    fetch_boundary()
    fetch_childcare()
    fetch_spop()
