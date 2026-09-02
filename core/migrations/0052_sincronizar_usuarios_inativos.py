from django.db import migrations


def sincronizar_status(apps, schema_editor):
    Piloto = apps.get_model("core", "Piloto")
    User = apps.get_model("auth", "User")
    for piloto in Piloto.objects.exclude(user_id=None).iterator():
        User.objects.filter(pk=piloto.user_id).update(is_active=piloto.ativo)


class Migration(migrations.Migration):
    dependencies = [("core", "0051_importacaolog_baterias_detectadas")]

    operations = [migrations.RunPython(sincronizar_status, migrations.RunPython.noop)]
