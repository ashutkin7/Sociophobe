from django.db import migrations, models


def add_default_characteristics(apps, schema_editor):
    Characteristics = apps.get_model('accounts', 'Characteristics')

    default_characteristics = [
        ("Страна", "string", ""),
        ("Город", "string", ""),
        ("Возраст", "numeric", "1,200"),
        ("Пол", "choice", "м;ж"),
        ("Уровень образования", "choice", "Начальное общее образование (1–4 класса);Основное общее образование (9 классов);Среднее общее образование (11 классов);Среднее профессиональное образование (колледж);Высшее образование;Послевузовское образование"),
        ("Сфера занятости", "string", ""),
        ("Должность", "string", ""),
        ("Уровень дохода", "numeric", "0,1000000000"),
    ]

    for name, vtype, req in default_characteristics:
        Characteristics.objects.get_or_create(name=name, defaults={'value_type': vtype, 'requirements': req})


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_default_characteristics),
    ]
