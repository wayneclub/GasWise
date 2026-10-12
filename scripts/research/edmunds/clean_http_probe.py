"""Run from backend: uv run python ../scripts/research/edmunds/clean_http_probe.py.
No cookies, auth, API keys, browser state, or challenge handling.
"""
import json
import subprocess
from pathlib import Path
import httpx

BASE = 'https://www.edmunds.com/gateway/api/vehicle/v5/styles/401871900/features-specs'
FIELDS = 'styleAttributes,price,totalSeating,features.standard.Measurements,features.standard.Drive%20Train,features.standard.Fuel,features.standard.Engine,features.standard.Warranty'
URL = BASE + '?fields=' + FIELDS
rows = []
for name, url, headers in [
    ('httpx_default_full_fields', URL, {}),
    ('httpx_public_client_headers', BASE, {'x-artifact-id':'venom','x-artifact-version':'2.0.10659','x-client-action-name':'model_core_feature_specs.features.styles','Accept':'application/json'}),
    ('httpx_ordinary_browser_headers', URL, {'Accept':'application/json','Origin':'https://www.edmunds.com','Referer':'https://www.edmunds.com/toyota/camry/2021/features-specs/','User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36'}),
    ('httpx_observed_public_javascript', 'https://venom-assets.edmunds-media.com/model_core_feature_specs.chunk.ade5e65c29290137a961.js', {}),
]:
    with httpx.Client(timeout=20, auth=None, follow_redirects=False) as client:
        request = client.build_request('GET', url, headers=headers)
        assert not any(key in request.headers for key in ('cookie','authorization','x-api-key'))
        response = client.send(request)
        try:
            body = response.json()
            keys = list(body) if isinstance(body, dict) else None
        except ValueError:
            keys = None
        rows.append({'probe':name,'url':url,'status':response.status_code,'bytes':len(response.content),'json_keys':keys,'usable_vehicle_data':bool(keys and 'results' in keys),'credential_headers_present':False})
result = subprocess.run(['curl','--max-time','20','--silent','--show-error','--compressed','--http2',URL,'-w','\n%{http_code}'],capture_output=True,text=True,check=True)
body,status = result.stdout.rsplit('\n',1)
rows.append({'probe':'curl_native_http2','url':URL,'status':int(status),'bytes':len(body.encode()),'json_keys':list(json.loads(body)) if body.startswith('{') else None,'usable_vehicle_data':False,'credential_headers_present':False})
output = {'schema_reference':'public-runtime-evidence.json','scope':'Observed public URLs and normal headers only; no cookie/auth/session replay or challenge bypass. Browser access previously worked, but current browser surface unavailable.','probes':rows}
output_dir = Path(__file__).resolve().parents[3] / 'artifacts' / 'edmunds-research'
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / 'clean-http-results.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
