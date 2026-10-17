from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_incomeexpenseentry_tenant'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform_name', models.CharField(default='PharmaFlow BD', max_length=150)),
                ('platform_tagline', models.CharField(blank=True, default='ফার্মা ফ্লো • আধুনিক ফার্মেসি সফটওয়্যার', max_length=255)),
                ('logo', models.ImageField(blank=True, help_text='SaaS Main Platform Header Logo', null=True, upload_to='branding/')),
                ('logo_url', models.CharField(blank=True, help_text='Direct Logo URL or uploaded path', max_length=500, null=True)),
                ('support_phone', models.CharField(blank=True, default='01700-000000', max_length=50, null=True)),
                ('support_email', models.EmailField(blank=True, default='support@webkoders.com', max_length=254, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Platform Setting',
                'verbose_name_plural': 'Platform Settings',
            },
        ),
    ]

