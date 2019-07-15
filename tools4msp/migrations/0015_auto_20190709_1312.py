# Generated by Django 2.2.2 on 2019-07-09 13:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tools4msp', '0014_auto_20190709_1000'),
    ]

    operations = [
        migrations.CreateModel(
            name='MsfdEnv',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(max_length=100)),
                ('ecosystem_element', models.CharField(max_length=200)),
                ('broad_group', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='MsfdPres',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(max_length=100)),
                ('msfd_pressure', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='MsfdUse',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(max_length=100)),
                ('activity', models.CharField(max_length=200)),
            ],
        ),
        migrations.RenameField(
            model_name='sensitivity',
            old_name='pressure',
            new_name='pres',
        ),
        migrations.RenameField(
            model_name='weight',
            old_name='pressure',
            new_name='pres',
        ),
        migrations.RemoveField(
            model_name='env',
            name='code',
        ),
        migrations.RemoveField(
            model_name='env',
            name='description',
        ),
        migrations.RemoveField(
            model_name='env',
            name='id',
        ),
        migrations.RemoveField(
            model_name='env',
            name='label',
        ),
        migrations.RemoveField(
            model_name='pressure',
            name='code',
        ),
        migrations.RemoveField(
            model_name='pressure',
            name='description',
        ),
        migrations.RemoveField(
            model_name='pressure',
            name='id',
        ),
        migrations.RemoveField(
            model_name='pressure',
            name='label',
        ),
        migrations.RemoveField(
            model_name='use',
            name='code',
        ),
        migrations.RemoveField(
            model_name='use',
            name='description',
        ),
        migrations.RemoveField(
            model_name='use',
            name='id',
        ),
        migrations.RemoveField(
            model_name='use',
            name='label',
        ),
        migrations.AddField(
            model_name='env',
            name='codedlabel_ptr',
            field=models.OneToOneField(auto_created=True, default=1, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tools4msp.CodedLabel'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pressure',
            name='codedlabel_ptr',
            field=models.OneToOneField(auto_created=True, default=1, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tools4msp.CodedLabel'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='use',
            name='codedlabel_ptr',
            field=models.OneToOneField(auto_created=True, default=1, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='tools4msp.CodedLabel'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='env',
            name='msfd',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='tools4msp.MsfdEnv'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pressure',
            name='msfd',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='tools4msp.MsfdPres'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='use',
            name='msfd',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='tools4msp.MsfdUse'),
            preserve_default=False,
        ),
    ]