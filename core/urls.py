from django.urls import path
from . import views
from . import checklist_views
from . import solicitacao_views
from . import bateria_views
from . import inspecao_views
from . import documento_views
from . import alerta_views
from . import seguranca_views
from . import qualificacao_views
from . import telemetria_views
from . import componente_views
from . import perfil_views
from . import planejamento_views
from . import dji_cloud_views
from . import livestream_views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("solicitacoes/", solicitacao_views.solicitacoes_voo, name="solicitacoes_voo"),
    path("planejamentos/", planejamento_views.planejamentos, name="planejamentos"),
    path("planejamentos/novo/", planejamento_views.planejamento_novo, name="planejamento_novo"),
    path("planejamentos/api/visualizar-arquivo/", planejamento_views.planejamento_visualizar_arquivo, name="planejamento_visualizar_arquivo"),
    path("planejamentos/<int:pk>/", planejamento_views.planejamento_detalhe, name="planejamento_detalhe"),
    path("planejamentos/<int:pk>/editar/", planejamento_views.planejamento_editar, name="planejamento_editar"),
    path("planejamentos/<int:pk>/atualizar-previsao/", planejamento_views.planejamento_atualizar_previsao, name="planejamento_atualizar_previsao"),
    path("planejamentos/<int:pk>/baixar-kml/", planejamento_views.planejamento_baixar_kml, name="planejamento_baixar_kml"),
    path("planejamentos/<int:pk>/termo-coordenacao/", planejamento_views.planejamento_termo_coordenacao, name="planejamento_termo_coordenacao"),
    path("termos-coordenacao/<int:pk>/pdf/", planejamento_views.planejamento_termo_coordenacao_pdf, name="planejamento_termo_coordenacao_pdf"),
    path("planejamentos/api/buscar-local/", planejamento_views.planejamento_buscar_local, name="planejamento_buscar_local"),
    path("planejamentos/api/camadas-aeronauticas/", planejamento_views.planejamento_camadas_aeronauticas, name="planejamento_camadas_aeronauticas"),
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
    path("drones/<int:pk>/documentos/<int:documento_id>/excluir/", views.drone_documento_excluir, name="drone_documento_excluir"),
    path("drones/<int:pk>/status/", views.drone_status_atualizar, name="drone_status_atualizar"),
    path("drones/<int:pk>/historico/", views.drone_historico, name="drone_historico"),
    path("drones/<int:pk>/excluir/", views.drone_excluir, name="drone_excluir"),

    path("baterias/", bateria_views.baterias, name="baterias"),
    path("baterias/nova/", bateria_views.bateria_nova, name="bateria_nova"),
    path("baterias/<int:pk>/", bateria_views.bateria_detalhe, name="bateria_detalhe"),
    path("baterias/<int:pk>/editar/", bateria_views.bateria_editar, name="bateria_editar"),

    path("calendario/", views.calendario, name="calendario"),
    path("calendario/<int:pk>/checklist/", checklist_views.checklist_pre_voo, name="checklist_pre_voo"),
    path("calendario/nova/", views.alocacao_nova, name="alocacao_nova"),
    path("calendario/<int:pk>/editar/", views.alocacao_editar, name="alocacao_editar"),
    path("calendario/<int:pk>/excluir/", views.alocacao_excluir, name="alocacao_excluir"),
    path("calendario/<int:pk>/concluir/", views.alocacao_concluir, name="alocacao_concluir"),
    path("alocacoes/<int:alocacao_id>/pos-voo/", views.registro_pos_voo, name="registro_pos_voo"),

    path("relatorios/", views.relatorios, name="relatorios"),
    path("relatorios/exportar-pdf/", views.relatorios_exportar_pdf, name="relatorios_exportar_pdf"),
    path("relatorios/incidentes.pdf", views.relatorios_incidentes_pdf, name="relatorios_incidentes_pdf"),

    path("manutencoes/", views.manutencoes, name="manutencoes"),
    path("manutencoes/nova/", views.manutencao_nova, name="manutencao_nova"),
    path("manutencoes/<int:pk>/editar/", views.manutencao_editar, name="manutencao_editar"),
    path("manutencoes/<int:pk>/excluir/", views.manutencao_excluir, name="manutencao_excluir"),
    path("manutencoes/<int:pk>/concluir/", views.manutencao_concluir, name="manutencao_concluir"),
    path("inspecoes/", inspecao_views.planos_inspecao, name="planos_inspecao"),
    path("inspecoes/novo/", inspecao_views.plano_inspecao_novo, name="plano_inspecao_novo"),
    path("inspecoes/<int:pk>/editar/", inspecao_views.plano_inspecao_editar, name="plano_inspecao_editar"),
    path("inspecoes/<int:pk>/executar/", inspecao_views.plano_inspecao_executar, name="plano_inspecao_executar"),
    path("documentos/", documento_views.documentos, name="documentos"),
    path("documentos/novo/", documento_views.documento_novo, name="documento_novo"),
    path("documentos/<int:pk>/editar/", documento_views.documento_editar, name="documento_editar"),
    path("documentos/<int:pk>/excluir/", documento_views.documento_excluir, name="documento_excluir"),
    path("alertas/", alerta_views.alertas, name="alertas"),
    path("alertas/resolver/", alerta_views.alerta_resolver, name="alerta_resolver"),
    path("solicitacoes/<int:solicitacao_id>/risco/", seguranca_views.avaliacao_risco, name="avaliacao_risco"),
    path("solicitacoes/<int:solicitacao_id>/risco/pdf/", seguranca_views.avaliacao_risco_pdf, name="avaliacao_risco_pdf"),
    path("solicitacoes/<int:solicitacao_id>/risco/imprimir/", seguranca_views.avaliacao_risco_imprimir, name="avaliacao_risco_imprimir"),
    path("incidentes/", seguranca_views.incidentes, name="incidentes"),
    path("incidentes/novo/", seguranca_views.incidente_novo, name="incidente_novo"),
    path("incidentes/<int:pk>/editar/", seguranca_views.incidente_editar, name="incidente_editar"),
    path("meu-perfil-operacional/", qualificacao_views.meu_perfil_operacional, name="meu_perfil_operacional"),
    path("equipe-operacional/", qualificacao_views.equipe_operacional, name="equipe_operacional"),
    path("pilotos/<int:pk>/perfil-operacional/", qualificacao_views.perfil_operacional, name="perfil_operacional"),
    path("pilotos/<int:piloto_id>/qualificacoes/nova/", qualificacao_views.qualificacao_nova, name="qualificacao_nova"),
    path("qualificacoes/<int:pk>/editar/", qualificacao_views.qualificacao_editar, name="qualificacao_editar"),
    path("telemetria/", telemetria_views.telemetria_lista, name="telemetria_lista"),
    path("telemetria/importar/", telemetria_views.telemetria_importar, name="telemetria_importar"),
    path("telemetria/modelo.csv", telemetria_views.telemetria_modelo_csv, name="telemetria_modelo_csv"),
    path("telemetria/<int:pk>/", telemetria_views.telemetria_detalhe, name="telemetria_detalhe"),
    path("telemetria/<int:pk>/excluir/", telemetria_views.telemetria_excluir, name="telemetria_excluir"),
    path("componentes/", componente_views.componentes, name="componentes"),
    path("componentes/novo/", componente_views.componente_novo, name="componente_novo"),
    path("componentes/<int:pk>/", componente_views.componente_detalhe, name="componente_detalhe"),
    path("componentes/<int:pk>/editar/", componente_views.componente_editar, name="componente_editar"),
    path("componentes/<int:pk>/qr.png", componente_views.componente_qr, name="componente_qr"),
    path("identificar/<uuid:token>/", componente_views.componente_detalhe, name="componente_por_qr"),
    path("meu-perfil/", perfil_views.perfil_usuario, name="meu_perfil"),
    path("usuarios/<int:pk>/perfil/", perfil_views.perfil_usuario, name="perfil_usuario"),
    path("usuarios/<int:pk>/relatorio.pdf", qualificacao_views.perfil_operacional_pdf, name="perfil_operacional_pdf"),
    path("usuarios/<int:pk>/documentos/novo/", perfil_views.documento_perfil_novo, name="documento_perfil_novo"),
    path("qualificacoes-operacionais/<int:pk>/editar/", perfil_views.documento_perfil_editar, name="documento_perfil_editar"),
    path("integracoes/dji/", dji_cloud_views.dji_cloud_configuracao, name="dji_cloud_configuracao"),
    path("livestream/", livestream_views.transmissoes_ao_vivo, name="livestream"),
    path("integracoes/dji/pilot/login/", dji_cloud_views.DJIPilotLoginView.as_view(), name="dji_pilot_login"),
    path("integracoes/dji/pilot/", dji_cloud_views.dji_pilot_portal, name="dji_pilot_portal"),
    path("integracoes/dji/pilot/identificar/", dji_cloud_views.dji_pilot_identificar, name="dji_pilot_identificar"),
    path("integracoes/dji/mqtt/auth/", dji_cloud_views.dji_mqtt_autorizar, name="dji_mqtt_autorizar"),
    path("integracoes/dji/pilot/livestream/preparar/", dji_cloud_views.dji_livestream_preparar, name="dji_livestream_preparar"),
    path("integracoes/dji/pilot/livestream/status/", dji_cloud_views.dji_livestream_status, name="dji_livestream_status"),
]
