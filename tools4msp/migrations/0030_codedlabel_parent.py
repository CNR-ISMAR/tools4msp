# Generated by Django 2.2.13 on 2022-05-02 15:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0029_auto_20220430_2131'),
    ]

    operations = [
        migrations.AddField(
            model_name='codedlabel',
            name='parent',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children_set', to='tools4msp.CodedLabel'),
        ),
    ]
