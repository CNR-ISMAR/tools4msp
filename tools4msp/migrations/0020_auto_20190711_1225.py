# Generated by Django 2.2.2 on 2019-07-11 12:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0019_casestudy_import_domain_area'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='domainarea',
            options={'ordering': ['label']},
        ),
    ]