# Generated by Django 2.2.13 on 2022-06-17 12:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0037_auto_20220503_0850'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='env',
            options={'ordering': ['path'], 'verbose_name': 'Environmental receptor'},
        ),
        migrations.AlterModelOptions(
            name='pressure',
            options={'ordering': ['path']},
        ),
        migrations.AlterModelOptions(
            name='use',
            options={'ordering': ['path']},
        ),
        migrations.AddField(
            model_name='codedlabel',
            name='fa_class',
            field=models.CharField(default='fa-circle', max_length=64),
        ),
    ]