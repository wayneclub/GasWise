"""uv run --with curl-cffi --with beautifulsoup4 python this_file.py.
Public product identity only; no login/auth/API key/cookie replay.
"""
import json
from pathlib import Path
from bs4 import BeautifulSoup
from curl_cffi import requests

root=Path(__file__).resolve().parents[3] / "artifacts" / "amazon-research"
root.mkdir(parents=True, exist_ok=True)
rows=[]
for asin in ('B019IPTB0W','B002EBSLA4'):
    url=f'https://www.amazon.com/dp/{asin}'
    response=requests.get(url,impersonate='chrome',headers={'Accept':'text/html'},timeout=25,discard_cookies=True,allow_redirects=False)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,'html.parser')
    title=soup.select_one('#productTitle')
    assert title is not None,'No product page title; do not parse challenge/search page.'
    allowed={'Brand','Brand Name','Manufacturer','Manufacturer Part Number','Part Number','Item model number','Model Number','ASIN','Item Type Name'}
    fields={}
    evidence=[]
    for table in soup.select('table.a-keyvalue, table.prodDetTable'):
        for tr in table.select('tr'):
            th,td=tr.select_one('th'),tr.select_one('td')
            if th is None or td is None: continue
            label=th.get_text(' ',strip=True)
            if label in allowed:
                value=td.get_text(' ',strip=True)
                fields[label]=value
                evidence.append({'label':label,'value':value,'selector':'table.a-keyvalue.prodDetTable tr th/td'})
    echoed=list(dict.fromkeys(x.get('value')for x in soup.select('input[name="ASIN"]')if x.get('value')))
    assert asin in echoed and fields.get('ASIN')==asin,'Product ASIN identity mismatch.'
    data={'source_url':url,'http_status':response.status_code,'response_bytes':len(response.content),'requested_asin':asin,'page_asin':echoed,'title':title.get_text(' ',strip=True),'fields':fields,'field_evidence':evidence,'cookies_replayed':False,'auth_used':False,'limitation':'Product listing metadata is observed identity, not proof of compatibility. Manufacturer Part Number and Model Number may differ; retain both.'}
    root.joinpath(f'{asin}-identity.json').write_text(json.dumps(data,indent=2)+'\n')
    fixture=BeautifulSoup('<html><body></body></html>','html.parser')
    t=fixture.new_tag('span',id='productTitle');t.string=data['title'];fixture.body.append(t)
    tbl=fixture.new_tag('table',attrs={'class':'a-keyvalue prodDetTable'});fixture.body.append(tbl)
    for label,value in fields.items():
        tr=fixture.new_tag('tr');th=fixture.new_tag('th');th.string=label;td=fixture.new_tag('td');td.string=value;tr.append(th);tr.append(td);tbl.append(tr)
    inp=fixture.new_tag('input',attrs={'name':'ASIN','value':asin});fixture.body.append(inp)
    root.joinpath(f'{asin}-identity-minimal.html').write_text(str(fixture)+'\n')
    rows.append(data)
print(json.dumps(rows,indent=2))
