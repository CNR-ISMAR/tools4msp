# Generated by Django 2.2.2 on 2020-03-20 10:06

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0020_auto_20191218_0954'),
    ]

    operations = [
        migrations.AddField(
            model_name='casestudy',
            name='gridinfo',
            field=jsonfield.fields.JSONField(blank=True, null=True),
        ),
    ]