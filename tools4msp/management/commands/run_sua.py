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

    def handle(self, *args, **options):
        nparams = options['nparams']
        nruns = options['nruns']
        for run_id in options['run_ids']:
            self.stdout.write('Starting SUA analysis CaseStudyRun={} ...'.format(run_id))
            _run_sua(run_id, nparams, nruns)
            self.stdout.write(self.style.SUCCESS('Successfully saved SUA results CaseStudyRun={}\t'.format(run_id)))
