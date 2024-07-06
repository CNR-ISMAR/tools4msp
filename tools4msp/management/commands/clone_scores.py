from django.core.management.base import BaseCommand, CommandError
from tools4msp.models import Use, Context, MUCPotentialConflict, Weight, Sensitivity, Pressure

class Command(BaseCommand):
    help = 'Clones an existing Use including the pressure weights and the MUC potential conflict scores'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'context',
            help='label:label'
        )
        parser.add_argument(
            '--use',
            help='CODE:CODE:MUCscore'
        )
        parser.add_argument(
            '--pres',
            help='CODE:CODE'
        )
        parser.add_argument(
            '--env',
            help='CODE:CODE'
        )
        parser.add_argument(
                        '--overwrite',
                        action='store_true',
                        help='Overwrite existing scores',
                    )
        parser.add_argument(
                        '--list',
                        action='store_true',
                        help='Lists existing uses and exit',
                    )
        
    def handle(self, *args, **options):
        context = None
            
        if options['list']:
            for u in Use.objects.all():
                self.stdout.write(u.code)
        else:
            old_context_label, new_context_label = options['context'].split(":")
            overwrite = options['overwrite']
            if options['use'] is not None:
                old_use_code, new_use_code, old_new_muc_conflict = options['use'].split(":")
            else:
                old_use_code, new_use_code, old_new_muc_conflict = None, None, None
            if options['pres'] is not None:
                old_pres_code, new_pres_code = options['pres'].split(":")
            else:
                old_pres_code, new_pres_code = None, None
            if options['env'] is not None:
                old_env_code, new_env_code = options['env'].split(":")
            else:
                old_env_code, new_env_code = None, None

            clone_muc = True
            clone_weights = True
            clone_sensitivities = True

            # if old_context == new_contex we use, pres or env must be not null
            if old_context_label == new_context_label:
                clone_muc = False
                clone_weights = False
                clone_sensitivities = False
                if new_use_code is not None and old_use_code != new_use_code:
                    clone_muc = True
                    clone_weights = True
                if new_pres_code is not None and old_pres_code != new_pres_code:
                    clone_weights = True
                    clone_sensitivities = True
                if new_env_code is not None and old_env_code != new_env_code:
                    clone_sensitivities = True

            if clone_muc:
                self.stdout.write('Cloning MUC potential conflict')
                cloned = MUCPotentialConflict.objects.clone_muc_potential_conflicts(
                    old_context_label, new_context_label,
                    old_use_code, new_use_code,
                    old_new_muc_conflict,
                    overwrite
                )
                for c in cloned:
                    self.stdout.write('\t{} {}'.format(c[0], c[1]))

            if clone_weights:
                self.stdout.write('Cloning pressure weights')
                cloned = Weight.objects.clone_weights(
                    old_context_label, new_context_label,
                    old_use_code, new_use_code,
                    old_pres_code, new_pres_code,
                    overwrite
                )
                for c in cloned:
                    self.stdout.write('\t{} {}'.format(c[0], c[1]))

            if clone_sensitivities:
                self.stdout.write('Cloning sensitivities')
                cloned = Sensitivity.objects.clone_sensitivities(
                    old_context_label, new_context_label,
                    old_pres_code, new_pres_code,
                    old_env_code, new_env_code,
                    overwrite
                )
                for c in cloned:
                    self.stdout.write('\t{} {}'.format(c[0], c[1]))

            # print(old_use_code, new_use_code)
            
            # if created:
            #    self.stdout.write('Weight score "{}" - "{}" has been created'.format(new_use.code, w.pres.code))


def clone_context(old_context_label, new_context_label, overwrite):
    if new_context_label is not None:
        context, created = Context.objects.get_or_create(label=new_label)


        
