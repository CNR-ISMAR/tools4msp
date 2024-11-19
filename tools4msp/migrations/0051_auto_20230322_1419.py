# Generated by Django 2.2.13 on 2023-03-22 14:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0050_casestudyinput_vizmode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casestudy',
            name='description',
            field=models.CharField(blank=True, help_text='CaseStudy description', max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='casestudyinput',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='casestudylayer',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='casestudyrun',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='casestudyruninput',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='casestudyrunlayer',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='casestudyrunoutput',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='casestudyrunoutputlayer',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
        migrations.AlterField(
            model_name='context',
            name='description',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
    ]