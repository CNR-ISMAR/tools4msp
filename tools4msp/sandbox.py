from os import path
from tools4msp.modules.cea import CEACaseStudy
module_class = CEACaseStudy
csdir = path.join(settings.MEDIA_ROOT,
                  'casestudy',
                  str(66))
module_cs = module_class(csdir=csdir)

module_cs.load_layers()
module_cs.load_grid()
module_cs.load_inputs()
for idx, l in module_cs.layers.iterrows():
    l.layer.fill_underlying_data(0)

import os
import matplotlib
import matplotlib.pyplot as plt
from django.db import connection
import pandas as pd
df = pd.read_pickle('/opt/tools4msp/temp/df.pickle')
matplotlib.use('module://backend_interagg')
df['count'].plot.hist()
plt.show()
