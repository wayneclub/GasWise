"""uv run --with curl-cffi python this_file.py. No cookies/auth/key.
Generic candidate search then catalog application hierarchy. Never infer exact
SKU from a cross-reference result; catalog application is YMM, not build proof.
"""
import json
from curl_cffi import requests
BASE='https://external-api.autozone.com/sls/'
HEADERS={'Accept':'application/json, text/plain, */*','Referer':'https://www.autozone.com/','X-Requested-By':'MF','sales-channel':'AZRMFWEB'}
COMMON={'country':'USA','customerType':'B2C','salesChannel':'ECOMM','preview':'false'}
def get(path,params):
    r=requests.get(BASE+path,params={**COMMON,**params},headers=HEADERS,impersonate='chrome',discard_cookies=True,allow_redirects=False,timeout=20)
    r.raise_for_status();return r.json()
def norm(value):return ''.join(c for c in value.upper() if c.isalnum())
brand,part='Mann-Filter','HU7025Z'
nav=get('pd/product-browse-search/v1/search-product',{'searchedKeyword':part})
record=nav['searchResults']['skuRecord']
results=get('b2c/product-discovery-browse-search-data/v2/product-shelves',{'canonicalPath':record['taxonomyPath'],'partGroupId':record['partGroupId'],'searchedKeyword':part,'pageNumber':1,'recordsPerPage':24})
exact=[r for r in results['productShelfResults']['skuRecords'] if norm(r.get('brandName',''))==norm(brand) and norm(r.get('partNumber',''))==norm(part)]
assert len(exact)==1,'Ambiguous/missing exact SKU; this is unknown, not does_not_fit.'
row=exact[0];p={'itemId':row['itemId'],'partGroupId':row['partGroupId']};path='pd/product-lookup/v1/product-vehicle-fitments'
makes=get(path,p);make=next(m for m in makes if m['name']=='Mercedes-Benz')
models=get(path,{**p,'makeId':make['id']});model=next(m for m in models if m['name']=='E400')
years=get(path,{**p,'makeId':make['id'],'modelId':model['id']})
print(json.dumps({'sku':{k:row[k]for k in ['brandName','partNumber','itemId','partGroupId','productDetailsPageUrl']},'complete_make_applications':makes,'model':model,'years':years,'verification_scope':'catalog_application','engine_verified':False,'fits_2018_e400_catalog':any(y['id']==2018 for y in years),'toyota_catalog_absent':not any(m['name']=='Toyota'for m in makes)},indent=2))
