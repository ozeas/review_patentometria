from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("s/<int:pk>/", views.study_detail, name="study"),
    path("s/<int:pk>/config/", views.study_config, name="study_config"),
    path("s/<int:pk>/tesauro/", views.thesaurus, name="thesaurus"),
    path("s/<int:pk>/tesauro/thesaurus.txt", views.thesaurus_download, name="thesaurus_download"),
    path("s/<int:pk>/exportar/<str:kind>.csv", views.export_dict, name="export_dict"),
    path("r/<int:pk>/", views.round_detail, name="round"),
    path("r/<int:pk>/upload/", views.round_upload, name="round_upload"),
    path("r/<int:pk>/executar/", views.round_run, name="round_run"),
    path("r/<int:pk>/familias/", views.family_list, name="families"),
    path("r/<int:pk>/f/<str:key>/", views.family_detail, name="family"),
    path("r/<int:pk>/triagem/<str:stage>/", views.triage_start, name="triage"),
    path("r/<int:pk>/ligacoes/", views.links, name="links"),
    path("r/<int:pk>/depositantes/", views.dict_applicants, name="dict_applicants"),
    path("r/<int:pk>/inventores/", views.dict_inventors, name="dict_inventors"),
    path("r/<int:pk>/indicadores/", views.indicators, name="indicators"),
    path("r/<int:pk>/vosviewer/", views.vos, name="vos"),
    path("r/<int:pk>/vosviewer/pacote.zip", views.vos_download, name="vos_download"),
    path("r/<int:pk>/planilha.xlsx", views.export_xlsx, name="export_xlsx"),
    path("r/<int:pk>/decisoes.csv", views.export_decisions, name="export_decisions"),
    path("r/<int:pk>/importar/", views.import_data, name="import"),
    path("arquivo/<int:pk>/remover/", views.file_delete, name="file_delete"),
    path("arquivo/<int:pk>/", views.file_edit, name="file_edit"),
]
