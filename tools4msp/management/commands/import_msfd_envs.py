from django.core.management.base import BaseCommand, CommandError
from tools4msp.models import MsfdEnv
import pandas as pd


class Command(BaseCommand):
    help = 'Import MFSD Envs from csv file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            help='CSV File'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']

        df = pd.read_csv(csv_file)
        df.rename(columns={'Theme': 'theme',
                           'Ecosystem component': 'ecosystem_component',
                           'Feature': 'feature',
                           'Element': 'element'},
                  inplace=True)
        # add additional rows
        gcols = ['theme', 'ecosystem_component']
        for r in df.groupby(gcols).size().reset_index()[gcols].to_dict('records'):
            df = df.append({'theme': r['theme'], 'ecosystem_component': r['ecosystem_component']}, ignore_index=True)

        gcols = ['theme', 'ecosystem_component', 'feature']
        for r in df.groupby(gcols).size().reset_index()[gcols].to_dict('records'):
            df = df.append({'theme': r['theme'], 'ecosystem_component': r['ecosystem_component'], 'feature': r['feature']}, ignore_index=True)

        for theme in df.theme.unique():
            df = df.append({'theme': theme}, ignore_index=True)

        print(df.tail(20))

        
        # print(df.columns)
        for id, r in df.iterrows():
            obj, created = MsfdEnv.objects.update_or_create(
                theme=r.theme,
                ecosystem_component=r.ecosystem_component,
                feature=r.feature,
                element=r.element
                )
            pass
            #self.stdout.write(f"{id}")
        # import default levels
            
        self.stdout.write(f"DONE {csv_file}")

        # for c in cls:
        #    pass
        #    # 
