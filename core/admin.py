from django.contrib import admin
from .models import Piloto, Drone, Voo, Alocacao, Manutencao

admin.site.register(Piloto)
admin.site.register(Drone)
admin.site.register(Voo)
admin.site.register(Alocacao)
admin.site.register(Manutencao)
