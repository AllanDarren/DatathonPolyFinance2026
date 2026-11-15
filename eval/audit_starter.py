"""Independent D audit of supplied snapshots. Never downloads or modifies starter data.

Usage: python3 eval/audit_starter.py --data-dir ../alphaforge_starter
Requires pandas for a second, separately expressed calculation of reference metrics.
"""
from __future__ import annotations

import argparse
import bisect
import calendar
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['assets_universe.csv', 'prices_daily.csv', 'corporate_actions.csv', 'fx_usdcad_daily.csv', 'macro_rates.csv', 'sources_metadata.csv', 'build_dataset.py', 'README.md', 'data_quality_warnings.txt']


def load(path):
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def series_metrics(points):
    values = [v for _, v in points]
    returns = [b / a - 1 for a, b in zip(values, values[1:])]
    peak = values[0]
    dd = 0.0
    peak_date = points[0][0]
    dd_peak, dd_trough, dd_peak_value = peak_date, peak_date, peak
    for day, value in points:
        if value >= peak:
            peak, peak_date = value, day
        if value / peak - 1 < dd:
            dd, dd_peak, dd_trough, dd_peak_value = value / peak - 1, peak_date, day, peak
    recovered = next((day for day, value in points if day > dd_trough and value >= dd_peak_value), None)
    years = []
    for year in range(int(points[0][0][:4]) + 1, int(points[-1][0][:4])):
        before = [(d, v) for d, v in points if d <= f'{year-1}-12-31']
        during = [(d, v) for d, v in points if f'{year}-01-01' <= d <= f'{year}-12-31']
        if before and during:
            years.append((year, during[-1][1] / before[-1][1] - 1))
    return dict(annualized_vol=statistics.stdev(returns)*math.sqrt(252), annualized_vol_365=statistics.stdev(returns)*math.sqrt(365), max_drawdown=dd, max_drawdown_abs=-dd, drawdown_peak_date=dd_peak, drawdown_trough_date=dd_trough, recovery_date=recovered, recovery_days=(date.fromisoformat(recovered)-date.fromisoformat(dd_peak)).days if recovered else None, return_5y=values[-1]/values[0]-1, calendar_year_return=dict(years).get(2022), worst_calendar_year_return=min(r for _, r in years))


def run(folder: Path):
    missing = [name for name in REQUIRED if not (folder/name).is_file()]
    if missing:
        raise ValueError(f'Fichiers du pack manquants : {missing}')
    hashes = {name: hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in REQUIRED}
    tables = {name: load(folder/name) for name in REQUIRED if name.endswith('.csv')}
    universe = {r['ticker']:r for r in tables['assets_universe.csv']}
    prices, fx, macro, actions = [tables[name] for name in ['prices_daily.csv','fx_usdcad_daily.csv','macro_rates.csv','corporate_actions.csv']]
    errors, warnings = [], []
    def check(ok, text):
        if not ok:
            errors.append(text)
    mapping=yaml.safe_load((ROOT/'rules/asset_class_mapping.yaml').read_text())
    policy=yaml.safe_load((ROOT/'rules/metric_policy.yaml').read_text())
    check(policy['annualized_vol']['periods_per_year']==252 and policy['annualized_vol']['ddof']==1 and policy['annualized_vol']['high_vol_threshold']==.30, 'Conventions métriques différentes de la référence v0.')
    mapped={}
    for ticker,asset in universe.items():
        candidates=[r for r in mapping['mappings'] if r['starter_asset_class']==asset['asset_class'] and all(asset[k]==r[k] for k in ['currency','sector'] if k in r)]
        check(len(candidates)==1, f'Classe sans correspondance unique : {ticker}')
        if len(candidates)==1: mapped[ticker]=candidates[0]['contract_asset_class']
    check(len(universe)==31 and len(universe)==len(tables['assets_universe.csv']), 'Univers non unique ou différent de 31 actifs.')
    check(len({(r['ticker'],r['date']) for r in prices})==len(prices), 'Prix dupliqués.')
    check(len({r['date'] for r in fx})==len(fx), 'Dates FX dupliquées.')
    check(len({(r['series_id'],r['date']) for r in macro})==len(macro), 'Macro dupliquée.')
    check(len({(r['ticker'],r['ex_date'],r['action']) for r in actions})==len(actions), 'Actions sur titres dupliquées.')
    by_ticker = defaultdict(list)
    zero_volume = []
    for r in prices:
        check(r['ticker'] in universe, f'Ticker hors univers : {r["ticker"]}')
        nums = [float(r[c]) for c in ['open','high','low','close','adj_close']]
        check(all(math.isfinite(v) and v>0 for v in nums), f'Prix invalide : {r["ticker"]}/{r["date"]}')
        op,hi,lo,cl,adj = nums
        check(lo-1e-5<=min(op,cl)<=max(op,cl)<=hi+1e-5, f'OHLC invalide : {r["ticker"]}/{r["date"]}')
        check(r['currency']==universe[r['ticker']]['currency'], f'Devise incohérente : {r["ticker"]}')
        check(math.isfinite(float(r['volume'])) and float(r['volume'])>=0, 'Volume invalide.')
        check('2021-11-12'<=r['date']<='2026-11-12', 'Prix hors fenêtre.')
        if float(r['volume'])==0:
            zero_volume.append(dict(ticker=r['ticker'],date=r['date']))
        by_ticker[r['ticker']].append((r['date'],adj))
    check(set(by_ticker)==set(universe), 'Actifs sans prix.')
    for points in by_ticker.values(): points.sort()
    fx.sort(key=lambda r:r['date'])
    for r in fx:
        check(math.isfinite(float(r['usdcad'])) and float(r['usdcad'])>0, 'FX invalide.')
        check(abs(float(r['cadusd'])-1/float(r['usdcad']))<=.00000051, 'Inverse FX incohérent.')
    for r in macro:
        check(math.isfinite(float(r['value'])), 'Valeur macro non finie.')
    for r in actions:
        check(r['ticker'] in universe and r['action'] in {'dividend','split'} and math.isfinite(float(r['value'])) and float(r['value'])>0, 'Action sur titre invalide.')
    fx_days = [r['date'] for r in fx]
    fx_rates = [float(r['usdcad']) for r in fx]
    metrics, coverage, contexts, filled = [], [], {}, Counter()
    for ticker, points in sorted(by_ticker.items()):
        coverage.append(dict(ticker=ticker,rows=len(points),first_date=points[0][0],last_date=points[-1][0],currency=universe[ticker]['currency'],contract_asset_class=mapped.get(ticker,'UNMAPPED')))
        check(points[0][0]=='2021-11-12' and points[-1][0]=='2026-11-12', f'Bornes incomplètes : {ticker}')
        for basis in ['listing','CAD']:
            converted=[]
            for day,value in points:
                if basis=='CAD' and universe[ticker]['currency']=='USD':
                    index=bisect.bisect_right(fx_days,day)-1
                    check(index>=0, f'FX initial absent : {day}')
                    if index<0: continue
                    if fx_days[index]!=day: filled[ticker]+=1
                    value*=fx_rates[index]
                converted.append((day,value))
            contexts[(ticker,basis)] = converted
            row=dict(ticker=ticker,basis=basis,currency=universe[ticker]['currency'] if basis=='listing' else 'CAD',n_prices=len(converted),**series_metrics(converted))
            metrics.append(row)
    warnings.append(f'{len(zero_volume)} ligne(s) de volume nul : {zero_volume}. Conservées dans les métriques de prix ajustés.')
    warnings.append('CNQ.TO : facteur 1,021 du 2022-08-22 non interprété et non réappliqué; vérification émetteur encore nécessaire.')
    warnings.append('Dates macro mensuelles de référence, pas de publication; valeurs révisées, impropres à un backtest point-in-time sans dates de diffusion.')
    warnings.append('Classes du pack différentes du contrat v0 : utiliser rules/asset_class_mapping.yaml.')
    # Independent references: stdlib calculations versus vector expressions in pandas.
    checks=[]
    def reference(id,label,primary,secondary,source,unit='fraction',approx=None,tolerance=None):
        check(math.isclose(primary,secondary,rel_tol=1e-10,abs_tol=1e-10), f'Désaccord entre méthodes : {id}')
        checks.append(dict(id=id,description=label,reference_stdlib=primary,reference_pandas=secondary,absolute_difference=abs(primary-secondary),unit=unit,source=source,application_value='',application_status='pending_no_application',context_reference='' if approx is None else approx,context_difference='' if approx is None else primary-approx,context_tolerance='' if tolerance is None else tolerance,context_status='not_compared' if approx is None else ('within_tolerance' if abs(primary-approx)<=tolerance else 'outside_tolerance')))
    df=pd.DataFrame(prices)
    df['adj_close']=df['adj_close'].astype(float)
    df['date']=pd.to_datetime(df['date'])
    df=df.pivot(index='date',columns='ticker',values='adj_close').sort_index()
    indexed={(r['ticker'],r['basis']):r for r in metrics}
    for ticker,approx in [('SPY',-.182),('QQQ',-.326),('AGG',-.130),('XBB.TO',-.117),('NVDA',-.50),('XOM',.87)]:
        s=df[ticker].dropna()
        val=s.loc[:'2022-12-31'].iloc[-1]/s.loc[:'2021-12-31'].iloc[-1]-1
        reference('R2022_'+ticker, f'{ticker} rendement 2022 en devise de cotation',indexed[ticker,'listing']['calendar_year_return'],val,'prices_daily.csv; adj_close; bornes dernières observations 2021 et 2022',approx=approx,tolerance=.005)
    for ticker,approx in [('NVDA',-.66),('BTC-USD',-.76),('TLT',-.44)]:
        s=df[ticker].dropna()
        reference('DD_'+ticker,f'{ticker} chute maximale en devise de cotation',indexed[ticker,'listing']['max_drawdown'],(s/s.cummax()-1).min(),'prices_daily.csv; adj_close; 2021-11-12/2026-11-12',approx=approx,tolerance=.005)
    for ticker,approx in [('SPY',.15),('NVDA',.50),('BTC-USD',.54)]:
        reference('VOL_'+ticker,f'{ticker} volatilité échantillonnale annualisée ×sqrt(252)',indexed[ticker,'listing']['annualized_vol'],df[ticker].dropna().pct_change(fill_method=None).dropna().std(ddof=1)*math.sqrt(252),'prices_daily.csv; adj_close; ddof=1; 252',approx=approx,tolerance=.005)
    monthly={}
    for ticker in by_ticker:
        end={}
        for day,val in by_ticker[ticker]: end[day[:7]]=val
        last_day=by_ticker[ticker][-1][0]
        if int(last_day[-2:]) < calendar.monthrange(int(last_day[:4]),int(last_day[5:7]))[1]:
            end.pop(last_day[:7],None)
        months=sorted(end)
        monthly[ticker]={month:end[month]/end[prev]-1 for prev,month in zip(months,months[1:])}
    for left,right,approx in [('QQQ','SPY',.91),('ESGV','SPY',.99),('BTC-USD','ETH-USD',.83),('BTC-USD','QQQ',.49)]:
        months=sorted(set(monthly[left])&set(monthly[right]))
        x=[monthly[left][m] for m in months]; z=[monthly[right][m] for m in months]
        # Direct centered-sum formula, independently of pandas.corr.
        xm,zm=statistics.mean(x),statistics.mean(z)
        corr=sum((a-xm)*(b-zm) for a,b in zip(x,z))/math.sqrt(sum((a-xm)**2 for a in x)*sum((b-zm)**2 for b in z))
        month_ends=df[[left,right]].resample('ME').last()
        month_ends=month_ends.loc[month_ends.index <= df.index.max()]
        other=month_ends.pct_change(fill_method=None).dropna().corr().loc[left,right]
        reference('CORR_'+left+'_'+right,f'{left}–{right} corrélation mensuelle ({len(months)} paires)',corr,other,'prices_daily.csv; dernières observations mensuelles; intersection',unit='correlation',approx=approx,tolerance=.02)
    for basis,approx in [('listing',.732),('CAD',.965)]:
        points=contexts['SPY',basis]
        if basis=='CAD':
            fx_s=pd.Series(fx_rates,index=pd.to_datetime(fx_days))
            s=df.SPY.dropna(); s=s*fx_s.reindex(s.index,method='ffill')
        else: s=df.SPY.dropna()
        reference('TOTAL_SPY_'+basis,f'SPY rendement fenêtre en {"USD" if basis=="listing" else "CAD"}',points[-1][1]/points[0][1]-1,s.iloc[-1]/s.iloc[0]-1,'prices_daily.csv'+('; fx_usdcad_daily.csv; report passé seulement' if basis=='CAD' else ''),approx=approx,tolerance=.005)
    september=sorted((r['date'],float(r['value'])) for r in macro if r['series_id']=='STATIC_TOTALCPICHANGE' and r['date'][5:7]=='09' and '2022'<=r['date'][:4]<='2026')
    check([d[:4] for d,_ in september]==['2022','2023','2024','2025','2026'], 'Chaîne IPC annuelle incomplète.')
    inflation=math.prod(1+v/100 for _,v in september)-1
    reference('CPI_CA_SEP21_SEP26','Inflation CA sept. 2021–sept. 2026, approximation par cinq taux annuels non chevauchants',inflation,pd.Series([1+v/100 for _,v in september]).prod()-1,'macro_rates.csv; STATIC_TOTALCPICHANGE; septembre 2022 à 2026',approx=.19,tolerance=.005)
    for pid,ticker in [('amira','NVDA'),('robert','ZST.TO'),('mateo','ESGV')]:
        rows=load(ROOT/f'rules/personas/{pid}_portfolio.csv')
        weight=next(float(r['montant']) for r in rows if r['ticker']==ticker)/sum(float(r['montant']) for r in rows)
        series=pd.Series({r['ticker']:float(r['montant']) for r in rows})
        reference('WEIGHT_'+pid,f'{pid} poids {ticker}',weight,series[ticker]/series.sum(),f'rules/personas/{pid}_portfolio.csv')
    # Actual, independently recomputed post-consideration inputs for role D rules.
    scenarios=[]
    for basis in ['listing','CAD']:
        for pid in ['robert','amira','mateo']:
            p=yaml.safe_load((ROOT/f'rules/personas/{pid}.yaml').read_text())
            rows=load(ROOT/f'rules/personas/{pid}_portfolio.csv')
            weights={r['ticker']:float(r['montant'])/100000 for r in rows}
            for after in [False,True] if pid!='mateo' else [False]:
                current=weights.get('NVDA',0)
                out={t:w*(1-.2)/(1-current) for t,w in weights.items() if t!='NVDA'} if after else dict(weights)
                if after: out['NVDA']=.2
                high_vol=sum(w for t,w in out.items() if indexed[t,basis]['annualized_vol']>.30)
                top3=sum(sorted(out.values(),reverse=True)[:3])
                metrics_input={k:indexed['NVDA',basis][k] for k in ['max_drawdown_abs','recovery_days']}
                metrics_input.update(position_weight_after=out.get('NVDA',0),high_vol_share=high_vol,top3_concentration=top3,asset_class='equity_us')
                hits=[]
                if after:
                    from check_role_d import matches
                    rules=yaml.safe_load((ROOT/'rules/coherence_rules.yaml').read_text())['rules']
                    hits=[r for r in rules if all(matches(c,dict(profile=p),metrics_input) for c in r['when'])]
                scenarios.append(dict(profile_id=pid,basis=basis,scenario='NVDA_final_20pct' if after else 'baseline',weights=out,high_vol_share=high_vol,high_vol_tickers=[t for t in out if indexed[t,basis]['annualized_vol']>.30],top3_concentration=top3,oversized_tickers=[t for t,w in out.items() if w>p['limits']['max_single_position']],metrics=metrics_input if after else None,rule_ids=[r['id'] for r in hits],verdict=('incoherent' if any(r['severity']=='high' for r in hits) else 'tension' if hits else 'coherent') if after else None))
    stats=dict(files={name:dict(sha256=hashes[name],rows=len(tables[name]) if name in tables else None) for name in REQUIRED},price_rows=len(prices),assets=len(universe),errors=errors,warnings=warnings,zero_volume=zero_volume,fx_carried_forward_rows=dict(filled),macro_coverage=[dict(series_id=s,rows=len(g),first_date=min(r['date'] for r in g),last_date=max(r['date'] for r in g)) for s in sorted({r['series_id'] for r in macro}) for g in [[r for r in macro if r['series_id']==s]]],checks=len(checks),independent_checks_passed=not any('Désaccord' in e for e in errors),application_validation='pending_no_application')
    report=ROOT/'eval/reports'; report.mkdir(exist_ok=True)
    check(all(len(monthly[t])==policy['monthly_correlation']['n_pairs'] for t in monthly), 'Nombre de rendements mensuels différent de la politique D.')
    write_csv(report/'asset_coverage.csv',coverage)
    write_csv(report/'asset_metrics.csv',metrics)
    write_csv(report/'market_validation.csv',checks)
    for name,value in [('starter_audit.json',stats),('portfolio_scenarios.json',scenarios)]:
        (report/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    # Formula workbook: raw inputs with formulas and cached stdlib results. No claim Excel was run.
    workbook(report/'validation_workbook.xml', contexts, september, checks)
    if errors: raise ValueError('\n'.join(errors))
    print(f'OK — {len(prices)} prix, {len(universe)} actifs, {len(checks)} comparaisons indépendantes. Rapports : {report}')
    for s in scenarios:
        print(s['profile_id'],s['basis'],s['scenario'],f"part volatile {s['high_vol_share']:.2%}",s['verdict'],s['rule_ids'])
    print('Écarts aux estimations AGENTS :',[(r['id'],r['reference_stdlib'],r['context_reference']) for r in checks if r['context_status']=='outside_tolerance'])


def workbook(path, contexts, september, checks):
    """Excel 2003 XML with auditable formulas; recalculation in a spreadsheet remains manual."""
    def cell(value,formula=None):
        numeric=isinstance(value,(int,float))
        f=' ss:Formula="'+escape(formula,{'"':'&quot;'})+'"' if formula else ''
        return f'<Cell{f}><Data ss:Type="{"Number" if numeric else "String"}">{escape(str(value))}</Data></Cell>'
    def row(values): return '<Row>'+''.join(cell(*v) if isinstance(v,tuple) else cell(v) for v in values)+'</Row>'
    sheets=[]
    def sheet(name,rows): sheets.append(f'<Worksheet ss:Name="{name}"><Table>'+''.join(rows)+'</Table></Worksheet>')
    sheet('Lire', [row(['Validation D — données de simulation fournies, 14 novembre 2026']),row(['Formules et caches générés par Python. Aucun recalcul Excel/LibreOffice exécuté.']),row(['Ouvrir dans un tableur, recalculer, puis comparer aux références. Application non disponible.']),row(['Prix : adj_close. Chutes : négatives. Volatilité échantillonnale ×sqrt(252).']),row(['IPC : cinq taux annuels de septembre NON chevauchants; arrondi 0,1 point.'])])
    for ticker in ['SPY','NVDA','QQQ']:
        pts=contexts[ticker,'listing']; rows=[row(['Date','Prix ajusté','Rendement','Sommet courant','Chute'])]; peak=0
        for i,(day,value) in enumerate(pts,2):
            peak=max(peak,value)
            ret=('',None) if i==2 else (value/pts[i-3][1]-1,'=RC[-1]/R[-1]C[-1]-1')
            # Blank first return is text, excluded by STDEV.
            rows.append(row([day,value,ret,(peak,'=MAX(R2C2:RC2)'),(value/peak-1,'=RC2/RC4-1')]))
        sheet(ticker,rows)
    # Paired monthly data calculated from raw snapshots; actual observation dates retained in separate price sheets.
    monthly={}
    for ticker in ['SPY','QQQ']:
        end={}
        for day,value in contexts[ticker,'listing']: end[day[:7]]=value
        last_day=contexts[ticker,'listing'][-1][0]
        if int(last_day[-2:]) < calendar.monthrange(int(last_day[:4]),int(last_day[5:7]))[1]:
            end.pop(last_day[:7],None)
        monthly[ticker]=end
    months=sorted(set(monthly['SPY'])&set(monthly['QQQ']))
    rows=[row(['Mois','SPY fin de mois','QQQ fin de mois','Rendement SPY','Rendement QQQ'])]
    for i,month in enumerate(months,2):
        vals=[month,monthly['SPY'][month],monthly['QQQ'][month]]
        for j,ticker in enumerate(['SPY','QQQ']):
            vals.append(('',None) if i==2 else (monthly[ticker][month]/monthly[ticker][months[i-3]]-1,f'=RC[{j-2}]/R[-1]C[{j-2}]-1'))
        # Both returns refer two columns left (D->B; E->C).
        if i>2:
            vals[3]=(vals[3][0],'=RC[-2]/R[-1]C[-2]-1'); vals[4]=(vals[4][0],'=RC[-2]/R[-1]C[-2]-1')
        rows.append(row(vals))
    sheet('Mensuel',rows)
    rows=[row(['Septembre','Taux annuel en points','Facteur'])]
    for day,value in september: rows.append(row([day,value,(1+value/100,'=1+RC[-1]/100')]))
    sheet('IPC',rows)
    refs={r['id']:r['reference_stdlib'] for r in checks}
    n=len(contexts['SPY','listing'])+1
    formulas=[('SPY 2022','R2022_SPY',None),('QQQ 2022','R2022_QQQ',None),('AGG 2022','R2022_AGG',None),('NVDA chute maximale','DD_NVDA',f'=MIN(NVDA!R2C5:R{n}C5)'),('SPY volatilité','VOL_SPY',f'=STDEV(SPY!R3C3:R{n}C3)*SQRT(252)'),('NVDA volatilité','VOL_NVDA',f'=STDEV(NVDA!R3C3:R{n}C3)*SQRT(252)'),('QQQ-SPY corrélation','CORR_QQQ_SPY',f'=CORREL(Mensuel!R3C4:R{len(months)+1}C4,Mensuel!R3C5:R{len(months)+1}C5)'),('SPY fenêtre USD','TOTAL_SPY_listing',f'=SPY!R{n}C2/SPY!R2C2-1'),('Inflation CA cumulée','CPI_CA_SEP21_SEP26','=PRODUCT(IPC!R2C3:R6C3)-1')]
    # Add raw AGG prices for a third full-year return.
    sheet('AGG',[row(['Date','Prix ajusté'])]+[row([d,v]) for d,v in contexts['AGG','listing']])
    summary=[row(['Mesure','Formule avec cache Python','Référence Python','Valeur application (à saisir)'])]
    for label,key,formula in formulas:
        if formula is None:
            ticker=key.split('_',1)[1];pts=contexts[ticker,'listing']
            start=max(i for i,(d,_) in enumerate(pts,2) if d<='2021-12-31')
            end=max(i for i,(d,_) in enumerate(pts,2) if d<='2022-12-31')
            formula=f'={ticker}!R{end}C2/{ticker}!R{start}C2-1'
        summary.append(row([label,(refs[key],formula),refs[key],'En attente']))
    for pid,ticker in [('amira','NVDA'),('robert','ZST.TO'),('mateo','ESGV')]:
        val=refs['WEIGHT_'+pid]
        summary.append(row([f'Poids {ticker} {pid}',(val,f'={int(round(val*100000))}/100000'),val,'En attente']))
    sheet('Comparaisons',summary)
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<?mso-application progid="Excel.Sheet"?>\n<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'+''.join(sheets)+'</Workbook>\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=ROOT.parent/'alphaforge_starter')
    args=parser.parse_args()
    run(args.data_dir.resolve())
