# Generated by Django 2.2.2 on 2019-07-13 07:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0022_auto_20190711_1317'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='env',
            options={'ordering': ['label'], 'verbose_name': 'Environmental receptor'},
        ),
        migrations.AlterModelOptions(
            name='msfdenv',
            options={'ordering': ['theme', 'ecosystem_element', 'broad_group'], 'verbose_name': 'MSFD environmental receptor'},
        ),
        migrations.AlterModelOptions(
            name='msfdpres',
            options={'ordering': ['theme', 'msfd_pressure'], 'verbose_name': 'MSFD pressure'},
        ),
        migrations.AlterModelOptions(
            name='msfduse',
            options={'ordering': ['theme', 'activity'], 'verbose_name': 'MSFD Activity', 'verbose_name_plural': 'MSFD Activities'},
        ),
        migrations.AlterModelOptions(
            name='weight',
            options={'verbose_name': 'Pressure weight'},
        ),
        migrations.AlterField(
            model_name='casestudy',
            name='import_domain_area',
            field=models.ManyToManyField(blank=True, to='tools4msp.DomainArea'),
        ),
    ]