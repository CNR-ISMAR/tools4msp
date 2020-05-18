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
