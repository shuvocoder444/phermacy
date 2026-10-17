from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_ledgercategory_incomeexpenseentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='incomeexpenseentry',
            name='tenant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ledger_entries', to='core.tenant'),
        ),
    ]

