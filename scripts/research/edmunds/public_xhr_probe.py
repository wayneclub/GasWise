"""Anonymous public XHR reproduction: uv run --with curl-cffi python this_file.py.
Fresh request per call, discard cookies, no login/auth/key/browser state.
"""
from pathlib import Path
import json
from curl_cffi import requests

ROOT=Path(__file__).resolve().parents[3] / "artifacts" / "edmunds-research"
ROOT.mkdir(parents=True, exist_ok=True)
BASE='https://www.edmunds.com/gateway/api'
FIELDS='styleAttributes,price,totalSeating,features.standard.Measurements,features.standard.Drive Train,features.standard.Fuel,features.standard.Engine,features.standard.Warranty'
results=[]
for make,model in [('toyota','camry'),('bmw','x3'),('bmw','m4')]:
    page=f'https://www.edmunds.com/{make}/{model}/2021/features-specs/'
    headers={'Accept':'application/json','Referer':page}
    def get(path,params):
        r=requests.get(BASE+path,params=params,headers=headers,impersonate='chrome',allow_redirects=False,discard_cookies=True,timeout=20)
        r.raise_for_status()
        data=r.json()
        assert data.get('results'),f'Empty data: {r.status_code}'
        return r,data
    response,metadata=get('/vehicle/v3/modelYears',{'makeNiceId':make,'modelNiceId':model,'year':2021,'pageSize':50,'pageNum':1})
    ROOT.joinpath(f'{make}-{model}-2021-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    info=metadata['results'][0]
    assert info['makeNiceId']==make and info['modelNiceId']==model and info['year']==2021
    for sub in info['submodels']:
        nice=sub['niceId']
        response,data=get(f'/vehicle/v5/makes/{make}/models/{model}/submodels/{nice}/years/2021/styles/features-specs',{'pageNum':1,'pageSize':50,'sortby':'price:asc','fields':FIELDS})
        ROOT.joinpath(f'{make}-{model}-2021-{nice}-specs.json').write_text(json.dumps(data,indent=2)+'\n')
        styles=[]
        for row in data['results']:
            standard=row['features']['standard']
            category=lambda c: {x['name']:x.get('value') for x in standard.get(c,[]) if 'name'in x}
            styles.append({'id':row['id'],'name':row['name'],'fuel':category('Fuel'),'engine':category('Engine'),'drivetrain':category('Drive Train')})
        results.append({'source_url':page,'api_url':response.url,'status':response.status_code,'bytes':len(response.content),'dataset':data.get('$dataset'),'make':info['makeName'],'model':info['modelName'],'year':info['year'],'submodel':nice,'totalNumber':data['totalNumber'],'totalPages':data['totalPages'],'styles':styles,'cookies_replayed':False,'auth_used':False})
ROOT.joinpath('public-xhr-results.json').write_text(json.dumps(results,indent=2)+'\n')
for r in results:
    print(r['make'],r['model'],r['submodel'],r['status'],r['bytes'],r['totalNumber'])
    for s in r['styles']: print(s['id'],s['name'],s['fuel'].get('Fuel type'))
