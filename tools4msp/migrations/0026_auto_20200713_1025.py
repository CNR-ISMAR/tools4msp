# Generated by Django 2.2.13 on 2020-07-13 10:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0025_auto_20200624_0959'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='mucpotentialconflict',
            unique_together={('context', 'use1', 'use2')},
        ),
    ]