from django.urls import path
from . import views
from . import solicitacao_views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("solicitacoes/", solicitacao_views.solicitacoes_voo, name="solicitacoes_voo"),
    path("solicitacoes/nova/", solicitacao_views.solicitacao_voo_nova, name="solicitacao_voo_nova"),
    path("solicitacoes/<int:pk>/editar/", solicitacao_views.solicitacao_voo_editar, name="solicitacao_voo_editar"),
    path("solicitacoes/<int:pk>/aprovar/", solicitacao_views.solicitacao_voo_aprovar, name="solicitacao_voo_aprovar"),
    path("solicitacoes/<int:pk>/rejeitar/", solicitacao_views.solicitacao_voo_rejeitar, name="solicitacao_voo_rejeitar"),
    path("solicitacoes/<int:pk>/cancelar/", solicitacao_views.solicitacao_voo_cancelar, name="solicitacao_voo_cancelar"),

    path("minha-agenda/", views.minha_agenda, name="minha_agenda"),

    path("primeiro-acesso/", views.primeiro_acesso, name="primeiro_acesso"),
    path("primeiro-acesso/continuar/", views.primeiro_acesso_continuar, name="primeiro_acesso_continuar"),

    path("voos/", views.voos, name="voos"),
    path("voos/novo/", views.voo_novo, name="voo_novo"),
    path("voos/<int:pk>/editar/", views.voo_editar, name="voo_editar"),
    path("voos/<int:pk>/excluir/", views.voo_excluir, name="voo_excluir"),

    path("pilotos/", views.pilotos, name="pilotos"),
    path("pilotos/novo/", views.piloto_novo, name="piloto_novo"),
    path("pilotos/<int:pk>/editar/", views.piloto_editar, name="piloto_editar"),
    path("pilotos/<int:pk>/excluir/", views.piloto_excluir, name="piloto_excluir"),

    path("drones/", views.drones, name="drones"),
    path("drones/novo/", views.drone_novo, name="drone_novo"),
    path("drones/<int:pk>/editar/", views.drone_editar, name="drone_editar"),
    path("drones/<int:pk>/status/", views.drone_status_atualizar, name="drone_status_atualizar"),
    path("drones/<int:pk>/historico/", views.drone_historico, name="drone_historico"),
    path("drones/<int:pk>/excluir/", views.drone_excluir, name="drone_excluir"),

    path("calendario/", views.calendario, name="calendario"),
    path("calendario/nova/", views.alocacao_nova, name="alocacao_nova"),
    path("calendario/<int:pk>/editar/", views.alocacao_editar, name="alocacao_editar"),
    path("calendario/<int:pk>/excluir/", views.alocacao_excluir, name="alocacao_excluir"),
    path("calendario/<int:pk>/concluir/", views.alocacao_concluir, name="alocacao_concluir"),

    path("relatorios/", views.relatorios, name="relatorios"),
    path("relatorios/exportar-pdf/", views.relatorios_exportar_pdf, name="relatorios_exportar_pdf"),

    path("manutencoes/", views.manutencoes, name="manutencoes"),
    path("manutencoes/nova/", views.manutencao_nova, name="manutencao_nova"),
    path("manutencoes/<int:pk>/editar/", views.manutencao_editar, name="manutencao_editar"),
    path("manutencoes/<int:pk>/excluir/", views.manutencao_excluir, name="manutencao_excluir"),
    path("manutencoes/<int:pk>/concluir/", views.manutencao_concluir, name="manutencao_concluir"),
]
