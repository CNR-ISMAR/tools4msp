# Generated by Django 2.2.13 on 2023-01-03 17:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0046_remove_sensitivity_impact_level_class'),
    ]

    operations = [
        migrations.RenameField(
            model_name='casestudyruninput',
            old_name='casestudy',
            new_name='casestudyrun',
        ),
        migrations.RenameField(
            model_name='casestudyrunlayer',
            old_name='casestudy',
            new_name='casestudyrun',
        ),
    ]