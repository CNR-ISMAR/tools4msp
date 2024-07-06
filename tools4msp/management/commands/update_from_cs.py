from django.core.management.base import BaseCommand, CommandError
from tools4msp.models import Use, Context, MUCPotentialConflict, Weight, Sensitivity, Pressure, CaseStudy

class Command(BaseCommand):
    help = 'Update the context pressures weights or sensitivities from the case study'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'casestudy',
            help='Case study id'
        )
        parser.add_argument(
            'context',
            help='Context label'
        )
        parser.add_argument(
            'matrix',
            help='weights or sensitivities'
        )
        
    def handle(self, *args, **options):
        csid = options['casestudy']
        context_label = options['context']
        matrix = options['matrix']
        cs = CaseStudy.objects.get(pk=csid)
        # context = cs.default_context
        module_cs = cs.module_cs
        module_cs.load_layers()
        module_cs.load_inputs()

        context = Context.objects.get(label=context_label)
        if matrix == 'weights':
            for idx, r in module_cs.weights.iterrows():
                u = Use.objects.get(code=r.usecode)
                p = Pressure.objects.get(code=r.precode)
                self.stdout.write('Updating {} {}'.format(r.usecode, r.precode))
                w, created = Weight.objects.get_or_create(context=context, use=u, pres=p, defaults={'weight': 0, 'distance': 0, 'confidence': 0})
                w.weight = r.weight
                w.distance = r.distance
                w.confidence = r.confidence                   
                w.save()
                if w.weight==0 and w.distance==0 and w.confidence==0:
                    w.delete()
                                
