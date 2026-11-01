"""행정동별 어린이집 공급 지표 계산 → data/ 의 웹앱용 파일 생성.

지표
- 공급률(밀도): 0~9세 생활인구 1,000명당 어린이집 정원
- 운영 유형 다양성: Gini–Simpson = 1 − Σ p_k² (p_k: 유형 k의 정원 비중)
- 형평성: 아동 인구가중 로렌츠 곡선과 Gini 계수 (서울 전체, 자치구별)
- 공공성: 국공립 정원 LQ = (동의 국공립 정원 비중) ÷ (서울의 국공립 정원 비중)
"""
import os, json
import numpy as np
import pandas as pd

os.environ.setdefault('PROJ_DATA', r'C:\Program Files\QGIS 4.2.1\share\proj')
os.environ.setdefault('GDAL_DATA', r'C:\Program Files\QGIS 4.2.1\apps\gdal\share\gdal')
import geopandas as gpd
from shapely.geometry import mapping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'cache')
DATA = os.path.join(ROOT, 'data')
os.makedirs(DATA, exist_ok=True)
log = open(os.path.join(CACHE, 'build_log.txt'), 'w', encoding='utf-8')


def L(*a):
    s = ' '.join(str(x) for x in a)
    log.write(s + '\n')
    log.flush()


# 1) 행정동 경계: 생활인구 행정동 체계(424개)에 맞춘다
g = gpd.read_file(os.path.join(CACHE, 'HangJeongDong_ver20250101.geojson'))
g = g[g['sidonm'] == '서울특별시'].copy()
g['code'] = g['adm_cd2'].str[:8]
g['name'] = g['adm_nm'].str.split().str[-1]
L('boundary dongs', len(g))

# 경계(2025-01-01)와 생활인구 행정동 코드가 다른 곳: 이름으로 확인한 대응
recode = {}
gb = g[g['sggnm'] == '강북구'].set_index('name')['code'].to_dict()
for old, nm in [('11305590', '번1동'), ('11305600', '번2동'), ('11305606', '번3동'),
                ('11305610', '수유1동'), ('11305620', '수유2동'), ('11305630', '수유3동')]:
    recode[gb[nm]] = old
gn = g[g['sggnm'] == '강남구'].set_index('name')['code'].to_dict()
recode[gn['개포3동']] = '11680740'  # 생활인구는 옛 일원2동 코드 사용
gd = g[g['sggnm'] == '강동구'].set_index('name')['code'].to_dict()
recode[gd['상일제1동']] = '11740520'
recode[gd['상일제2동']] = '11740520'
gr = g[g['sggnm'] == '구로구'].set_index('name')['code'].to_dict()
recode[gr['항동']] = gr['오류2동']
g['ucode'] = g['code'].map(lambda c: recode.get(c, c))
names = {'11740520': '상일동', gr['오류2동']: '오류2동·항동'}
L('recode', recode)

g5179 = g.to_crs(5179)
units = g5179.dissolve(by='ucode', aggfunc={'sggnm': 'first', 'name': 'first'}).reset_index()
units['name'] = units.apply(lambda r: names.get(r['ucode'], r['name']), axis=1)
units['area_km2'] = units.geometry.area / 1e6
L('analysis units', len(units))

# 2) 생활인구: 2026년 7월 31일간 03시 평균 (거주인구 대용)
sp = json.load(open(os.path.join(CACHE, 'spop_202607_03.json'), encoding='utf-8'))
recs = []
for dt, rows in sp.items():
    for r in rows:
        recs.append({'ucode': r['ADSTRD_CODE_SE'], 'date': dt,
                     'child': float(r['MALE_F0T9_LVPOP_CO']) + float(r['FEMALE_F0T9_LVPOP_CO']),
                     'total': float(r['TOT_LVPOP_CO'])})
pop = pd.DataFrame(recs).groupby('ucode')[['child', 'total']].mean().reset_index()
L('spop days', len(sp), 'units', len(pop))
miss_b = set(pop['ucode']) - set(units['ucode'])
miss_p = set(units['ucode']) - set(pop['ucode'])
L('unmatched spop', sorted(miss_b), 'unmatched boundary', sorted(miss_p))
assert not miss_b and not miss_p, '코드 대응 실패'

# 3) 어린이집: 운영 중(정상·재개)만, 좌표로 행정동 배정
cc = pd.DataFrame(json.load(open(os.path.join(CACHE, 'childcare.json'), encoding='utf-8')))
L('childcare status', cc['CRSTATUSNAME'].value_counts(dropna=False).to_dict())
cc = cc[cc['CRSTATUSNAME'].isin(['정상', '재개'])].copy()
cc['cap'] = pd.to_numeric(cc['CRCAPAT'], errors='coerce').fillna(0)
cc['cur'] = pd.to_numeric(cc['CRCHCNT'], errors='coerce').fillna(0)
pts = gpd.GeoDataFrame(cc, geometry=gpd.points_from_xy(cc['LO'].astype(float), cc['LA'].astype(float)), crs=4326).to_crs(5179)
j = gpd.sjoin(pts, units[['ucode', 'geometry']], how='left', predicate='within')
L('operating', len(cc), 'outside boundary', int(j['ucode'].isna().sum()))
outside = j[j['ucode'].isna()][['CRNAME', 'SIGUNNAME', 'CRADDR', 'LA', 'LO']]
L('outside list', outside.values.tolist())
j = j.dropna(subset=['ucode'])
L('type counts', j['CRTYPENAME'].value_counts().to_dict())

TYPES = ['국공립', '민간', '가정', '직장', '법인·단체등', '사회복지법인', '협동']
cap_t = j.pivot_table(index='ucode', columns='CRTYPENAME', values='cap', aggfunc='sum', fill_value=0)
for t in TYPES:
    if t not in cap_t.columns:
        cap_t[t] = 0
cap_t = cap_t[TYPES]
agg = j.groupby('ucode').agg(n=('cap', 'size'), cap=('cap', 'sum'), cur=('cur', 'sum')).reset_index()

df = units[['ucode', 'sggnm', 'name', 'area_km2']].merge(pop, on='ucode', how='left').merge(agg, on='ucode', how='left')
df = df.merge(cap_t.reset_index(), on='ucode', how='left')
df[['n', 'cap', 'cur'] + TYPES] = df[['n', 'cap', 'cur'] + TYPES].fillna(0)

# 4) 지표
df['supply'] = df['cap'] / df['child'] * 1000
p = df[TYPES].div(df['cap'].where(df['cap'] > 0), axis=0)
df['gs'] = 1 - (p ** 2).sum(axis=1)
df.loc[df['cap'] == 0, 'gs'] = np.nan
seoul_pub = df['국공립'].sum() / df['cap'].sum()
df['pub_share'] = df['국공립'] / df['cap'].where(df['cap'] > 0)
df['pub_lq'] = df['pub_share'] / seoul_pub
df['fill'] = df['cur'] / df['cap'].where(df['cap'] > 0)
df['density'] = df['n'] / df['area_km2']
seoul_child_share = df['child'].sum() / df['total'].sum()
df['child_lq'] = (df['child'] / df['total']) / seoul_child_share


def lorenz(sub):
    s = sub.sort_values('supply')
    x = np.concatenate([[0], s['child'].cumsum() / s['child'].sum()])
    y = np.concatenate([[0], s['cap'].cumsum() / s['cap'].sum()])
    gini = 1 - np.sum((x[1:] - x[:-1]) * (y[1:] + y[:-1]))
    return x, y, gini


x, y, gini = lorenz(df)

# 보조 분석: 직장어린이집 제외 공급률(도심 직장 보육 영향 분리), 생활인구 이상치 동 제외 민감도
df['cap_nowork'] = df['cap'] - df['직장']
df['supply_nowork'] = df['cap_nowork'] / df['child'] * 1000
_, _, gini_nowork = lorenz(df.assign(cap=df['cap_nowork'], supply=df['supply_nowork']))
df['pop_density'] = df['total'] / df['area_km2']
OUTLIER = ['11500593']  # 화곡8동: 03시 생활인구 88,525명 / 0.575㎢ (㎢당 15만 명)로 다른 동과 동떨어짐
df['note'] = np.where(df['ucode'].isin(OUTLIER), '생활인구 이상치 의심', '')
ok = df[~df['ucode'].isin(OUTLIER)]
_, _, gini_excl = lorenz(ok)
pos = df[df['cap'] > 0]
slope = float(np.polyfit(np.log(pos['child']), np.log(pos['cap']), 1)[0])
gu = []
for name, sub in df.groupby('sggnm'):
    _, _, gg = lorenz(sub)
    gu.append({'gu': name, 'gini': round(float(gg), 4), 'supply': round(float(sub['cap'].sum() / sub['child'].sum() * 1000), 1),
               'cap': int(sub['cap'].sum()), 'child': round(float(sub['child'].sum())), 'dongs': int(len(sub)),
               'pub_share': round(float(sub['국공립'].sum() / sub['cap'].sum()), 4)})
gu = sorted(gu, key=lambda r: r['gini'])

seoul_supply = df['cap'].sum() / df['child'].sum() * 1000
rho = df[['child', 'supply']].corr(method='spearman').iloc[0, 1]
rho_lq = df[['child_lq', 'supply']].corr(method='spearman').iloc[0, 1]
# 아동 집중(아동 LQ ≥ 1)과 공급률(서울 평균 이상) 교차 분류
df['quad'] = np.select(
    [(df['child_lq'] >= 1) & (df['supply'] < seoul_supply), (df['child_lq'] >= 1) & (df['supply'] >= seoul_supply),
     (df['child_lq'] < 1) & (df['supply'] < seoul_supply)],
    ['아동 많음·공급 부족', '아동 많음·공급 충분', '아동 적음·공급 부족'], default='아동 적음·공급 충분')

summary = {
    'n_units': int(len(df)), 'n_facilities': int(df['n'].sum()), 'cap': int(df['cap'].sum()), 'cur': int(df['cur'].sum()),
    'child': round(float(df['child'].sum())), 'seoul_supply': round(float(seoul_supply), 1), 'gini': round(float(gini), 4),
    'seoul_pub_share': round(float(seoul_pub), 4), 'seoul_fill': round(float(df['cur'].sum() / df['cap'].sum()), 4),
    'spearman_child_supply': round(float(rho), 3), 'spearman_childlq_supply': round(float(rho_lq), 3),
    'zero_cap_units': int((df['cap'] == 0).sum()),
    'gini_nowork': round(float(gini_nowork), 4), 'gini_excl_outlier': round(float(gini_excl), 4),
    'seoul_supply_nowork': round(float(df['cap_nowork'].sum() / df['child'].sum() * 1000), 1),
    'spearman_child_cap': round(float(df[['child', 'cap']].corr(method='spearman').iloc[0, 1]), 3),
    'spearman_child_supply_excl': round(float(ok[['child', 'supply']].corr(method='spearman').iloc[0, 1]), 3),
    'spearman_child_supply_nowork': round(float(df[['child', 'supply_nowork']].corr(method='spearman').iloc[0, 1]), 3),
    'loglog_slope_cap_child': round(slope, 3),
    'outlier_units': df[df['note'] != ''][['sggnm', 'name', 'total', 'area_km2', 'pop_density']].round(1).values.tolist(),
    'supply_quantiles': {q: round(float(df['supply'].quantile(q)), 1) for q in [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]},
    'gs_mean': round(float(df['gs'].mean()), 3), 'gs_quantiles': {q: round(float(df['gs'].quantile(q)), 3) for q in [0, 0.25, 0.5, 0.75, 1]},
    'quad_counts': df['quad'].value_counts().to_dict(),
    'type_cap': {t: int(df[t].sum()) for t in TYPES}, 'type_n': {k: int(v) for k, v in j['CRTYPENAME'].value_counts().items()},
    'outside_boundary': int(len(outside)), 'spop_days': len(sp), 'spop_period': '2026-07-01~2026-07-31 03시',
    'childcare_date': str(cc['DATASTDRDT'].mode().iloc[0]),
    'lorenz': {'x': [round(float(v), 4) for v in x], 'y': [round(float(v), 4) for v in y]},
}
for k in ['supply', 'gs', 'pub_lq', 'fill']:
    s = df.dropna(subset=[k]).sort_values(k)
    summary[f'{k}_low'] = s[['sggnm', 'name', k, 'child', 'cap']].head(10).round(3).values.tolist()
    summary[f'{k}_high'] = s[['sggnm', 'name', k, 'child', 'cap']].tail(10).iloc[::-1].round(3).values.tolist()

json.dump(summary, open(os.path.join(DATA, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(gu, open(os.path.join(DATA, 'gu.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 5) 웹 지도용 경계 (단순화, 좌표 5자리)
units4326 = units.copy()
units4326['geometry'] = units4326.geometry.simplify(15)
units4326 = units4326.to_crs(4326)
cols = ['ucode', 'sggnm', 'name', 'area_km2', 'child', 'total', 'n', 'cap', 'cur', 'supply', 'gs', 'pub_share', 'pub_lq',
        'fill', 'density', 'child_lq', 'quad', 'supply_nowork', 'note'] + TYPES
out = units4326[['ucode', 'geometry']].merge(df[cols], on='ucode')


def rnd(o):
    if isinstance(o, float):
        return round(o, 5)
    if isinstance(o, (list, tuple)):
        return [rnd(v) for v in o]
    return o


feats = []
for _, r in out.iterrows():
    props = {}
    for c in cols:
        v = r[c]
        if isinstance(v, (float, np.floating)):
            props[c] = None if np.isnan(v) else round(float(v), 4)
        elif isinstance(v, (np.integer,)):
            props[c] = int(v)
        else:
            props[c] = v
    geom = mapping(r.geometry)
    feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': geom['type'], 'coordinates': rnd(geom['coordinates'])}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, 'dong.geojson'), 'w', encoding='utf-8'),
          ensure_ascii=False, separators=(',', ':'))
df[cols].to_csv(os.path.join(DATA, 'dong_indicators.csv'), index=False, encoding='utf-8-sig')
L('summary', json.dumps({k: v for k, v in summary.items() if k != 'lorenz'}, ensure_ascii=False))
L('geojson bytes', os.path.getsize(os.path.join(DATA, 'dong.geojson')))
log.close()
print('done')
