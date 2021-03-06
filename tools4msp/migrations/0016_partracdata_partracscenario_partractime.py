# Generated by Django 2.2.2 on 2019-10-10 14:47

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0015_auto_20191009_1655'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartracScenario',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='PartracTime',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference_time', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='PartracData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('particle_id', models.IntegerField()),
                ('geo', django.contrib.gis.db.models.fields.PointField(help_text='point geometry(Lat Log WGS84)', srid=4326)),
                ('depth', models.FloatField()),
                ('reference_time', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tools4msp.PartracTime')),
                ('scenario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tools4msp.PartracScenario')),
            ],
        ),
    ]
