import os
import matplotlib.pyplot as plt
import requests
import time
from tools4msp_apiclient import Tools4MSPApiCLient

APIURL = "https://api.tools4msp.eu/docs/v2/"
TOKEN = os.getenv("TOOLS4MSPAPI_TOKEN")

tclient = Tools4MSPApiCLient(APIURL, TOKEN)

# create a new CaseStudy
print("Creating Case Study")
params = {'label': 'Case Study - Test API',
          'description': 'Case Study description',
          'module': 'cea',
          'cstype': 'customized',
          'resolution': 1000,
          'domain_area_terms': [178], # Strait of Sicily https://api.tools4msp.eu/api/v2/domainareas/188/
          }
cs = tclient.client.action(tclient.schema, ['casestudies', 'create'],
                           params=params)
csid = cs['id']

# SET Context
print("Setting Context")
params = {
    'id': csid,
    'context_label': 'CEA-SLOVENIA-MSP'
}
tclient.client.action(tclient.schema,
                      ['casestudies', 'setcontext'],
                      params=params
                      )


# print Case Study info
print("Case Study Info")
print("Id:", csid)
print("Label:", cs['label'])
print("Description:", cs['description'])
# print layers
print("Layers")
for l in cs['layers']:
    print("\t", l['code'])

# upload a "Human use" layer
print("Uploading Human use")
code = 'B-TRAWL'
clurl = tclient.client.action(tclient.schema, ['codedlabels', 'read'],
                              params={'code': code})['url']
tclient.create_and_upload('layers', csid, clurl,
                          'data/use-B-TRAWL.tiff',
                          replace=True)

# upload an "Environmental component" layer
print("Uploading Env component")
code = 'NV'
clurl = tclient.client.action(tclient.schema, ['codedlabels', 'read'],
                              params={'code': code})['url']
tclient.create_and_upload('layers', csid, clurl,
                          'data/env-NV.tiff',
                          replace=True)

# run the case study async mode
print("Run the case study async mode")
params = {
    'id': csid,
}
csrun = tclient.client.action(tclient.schema,
                               ['casestudies', 'asyncrunpost'],
                               params=params
                               )
csrunid = csrun['run_id']
print("\tRun ID=", csrunid)

print("Check for status: max 5 tentatives")
ncheck = 0
while True:
    ncheck += 1
    if ncheck > 5:
        print("Escaping now")
        break
    time.sleep(2)
    # check the casestudyrun status
    csrun = tclient.client.action(tclient.schema, ['casestudyruns', 'read'],
                                  params={'id': csrunid})
    print("\tRun status", csrun['runstatus'])  # 0 in progress, 1 done
    print("\tRun errors", csrun['runerror'])  # 0 in progress, 1 done
    if csrun['runstatus'] > 0:
        break

# download an output layer
print("Downloading layer result")
raster = tclient.get_outputlayer(csrunid, 'CEASCORE')
assert 212918 < raster.max() < 212919

# download an output json
print("Downloading json result")
fpath = tclient.get_output(csrunid, 'VULNERABILITY-PROF')
output =requests.get(fpath).json()

# remove the case study
print("Removing the case study")
tclient.client.action(tclient.schema, ['casestudies', 'delete'],
                              params={'id': csid})

