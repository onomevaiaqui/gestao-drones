from django.contrib import admin
from .models import DJIDock, DJIDockArquivo, DJIDockComando, DJIDockEvento, DJIDockMissao, DJIDRCComando, DJIDRCSessao, Piloto, Drone, Voo, Alocacao, Manutencao, TransmissaoAoVivo

admin.site.register(Piloto)
admin.site.register(Drone)
admin.site.register(Voo)
admin.site.register(Alocacao)
admin.site.register(Manutencao)
admin.site.register(TransmissaoAoVivo)
admin.site.register(DJIDock)
admin.site.register(DJIDockEvento)
admin.site.register(DJIDockComando)
admin.site.register(DJIDockMissao)
admin.site.register(DJIDockArquivo)
admin.site.register(DJIDRCSessao)
admin.site.register(DJIDRCComando)
