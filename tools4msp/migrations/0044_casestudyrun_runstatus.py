# Generated by Django 2.2.13 on 2022-10-21 21:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0043_auto_20221021_0816'),
    ]

    operations = [
        migrations.AddField(
            model_name='casestudyrun',
            name='runstatus',
            field=models.IntegerField(choices=[(0, 'running'), (1, 'completed'), (2, 'error')], default=0),
        ),
    ]
