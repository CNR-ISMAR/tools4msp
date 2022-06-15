from django.core.management.base import BaseCommand, CommandError
from tools4msp.models import _run_sua


class Command(BaseCommand):
    help = 'Run uncertainty and sensitivity analysis over a CaseStudyRun'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'run_ids',
            nargs="+",
            type=int,
        )
        parser.add_argument(
            '--nparams',
            type=int,
            default=10,
        )
        parser.add_argument(
            '--nruns',
            type=int,
            default=50,
        )

        parser.add_argument(
            '--njobs',
            type=int,
            default=1,
        )

        parser.add_argument(
            '--nogroup',
            action='store_true',
        )

        parser.add_argument(
            '--second_order',
            action='store_false',
        )

    def handle(self, *args, **options):
        nparams = options['nparams']
        nruns = options['nruns']
        njobs = options['njobs']
        bygroup = not options['nogroup']
        calc_second_order = not options['second_order']
        for run_id in options['run_ids']:
            self.stdout.write('Starting SUA analysis CaseStudyRun={} ...'.format(run_id))
            _run_sua(run_id, nparams, nruns, bygroup=bygroup,
                     njobs=njobs, calc_second_order=calc_second_order)
            self.stdout.write(self.style.SUCCESS('Successfully saved SUA results CaseStudyRun={}\t'.format(run_id)))
