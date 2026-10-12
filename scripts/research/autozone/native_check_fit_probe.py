"""Anonymous native fitment reproduction, run from backend using curl-cffi.
Supply GASWISE_TEST_VIN, or GASWISE_TEST_PLATE and GASWISE_TEST_STATE, in the environment. Never
prints/stores plate/VIN, never mutates garage/account, no cookie/auth replay.
"""
import json
import os
from curl_cffi import requests
from gaswise.providers.vehicles.plate import AutoZonePlateProvider

BASE='https://external-api.autozone.com/sls/'
HEADERS=AutoZonePlateProvider.headers

def get(url,params):
    r=requests.get(url,params=params,headers=HEADERS,impersonate='chrome',discard_cookies=True,allow_redirects=False,timeout=20)
    if r.status_code != 200: raise RuntimeError(f'Provider HTTP status {r.status_code}')
    return r.json()

lookup={'callingClient':'DIY-DESKTOP','country':'USA'}
if os.environ.get('GASWISE_TEST_VIN'):
    lookup['vin']=os.environ['GASWISE_TEST_VIN']
else:
    lookup.update({'licensePlate':os.environ['GASWISE_TEST_PLATE'],'state':os.environ['GASWISE_TEST_STATE']})
record=get(AutoZonePlateProvider.url,lookup)
if len(record)!=1: raise RuntimeError('Vehicle identity is not unique')
attrs=record[0]['acesVehicleAttributes']
# Native frontend module 61999 filters scalar Id/ID questions and serializes ||.
# Lookup nests engine IDs, so flatten them into the native scalar question map.
flat={**attrs,**attrs.get('engineIds',{})}
excluded={'acesVehicleId','partsProVehicleId','vehicleTypeId','catalogVehicleId','vehicleId','makeId','modelId'}
questions='||'.join(f'{k}:{v}'for k,v in flat.items()if ('Id'in k or'ID'in k)and k not in excluded and isinstance(v,(str,int)))
common={'country':'USA','preview':'false','year':attrs['year'],'makeId':attrs['makeId'],'modelId':attrs['modelId'],'vehicleTypeId':attrs['vehicleTypeId'],'vehicleQuestions':questions}
# Known products are research examples, not an implementation lookup registry.
for label,path in [('positive','/p/mann-filter-engine-oil-filter-hu7025z/1576960'),('negative','/p/stp-engine-oil-filter-s45023/1117175')]:
    result=get(BASE+'b2c/product-discovery-product-data/v2/products',{**common,'productDetailsPageUrl':path,'partGroupId':'azpg1622'})
    for product in result.get('pdpResults',{}).get('products',[]):
        print(json.dumps({'case':label,'supplier_native_context_sent':True,'engine_attributes_present':all(k in flat for k in ['engineBaseId','aspirationId','engineDesignationId']),'product':{k:product.get(k)for k in ['itemId','brandName','partNumber','vehicleFit','vehicleFitment','displayNotes','displayNotesTypes']}}))
