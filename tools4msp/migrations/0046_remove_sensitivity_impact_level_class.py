# Generated by Django 2.2.13 on 2022-12-07 17:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0045_sensitivity_impact_level_class'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sensitivity',
            name='impact_level_class',
        ),
    ]
