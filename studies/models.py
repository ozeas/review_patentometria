"""Modelos persistentes.

- ``Study`` guarda a configuração e tudo que é reaproveitado entre rodadas:
  decisões de elegibilidade, ligações manuais, dicionários e tesauro.
  Decisões e ligações são ancoradas em números de publicação normalizados,
  de modo que uma nova coleta herda o que já foi decidido.
- ``Round`` é uma rodada de coleta (exportações de uma data).
"""
import copy

from django.db import models

from core.pipeline import DEFAULT_CONFIG
from core.records import SOURCE_LABELS

SOURCE_CHOICES = [(k, v) for k, v in SOURCE_LABELS.items()]


def default_config():
    return copy.deepcopy(DEFAULT_CONFIG)


class Study(models.Model):
    name = models.CharField("nome", max_length=200)
    description = models.TextField("descrição", blank=True)
    config = models.JSONField("configuração", default=default_config)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "estudo"
        ordering = ["-created"]

    def __str__(self):
        return self.name

    @property
    def cfg(self):
        return {**default_config(), **(self.config or {})}


class Round(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="rounds")
    label = models.CharField("rótulo", max_length=200)
    collection_date = models.DateField("data da coleta", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    created = models.DateTimeField(auto_now_add=True)
    last_run = models.DateTimeField(null=True, blank=True)
    run_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "rodada de coleta"
        verbose_name_plural = "rodadas de coleta"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.study} · {self.label}"


def upload_path(instance, filename):
    return f"rodadas/{instance.round_id}/{filename}"


class SourceFile(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="files")
    source = models.CharField("base", max_length=20, choices=SOURCE_CHOICES)
    recorte = models.CharField("recorte", max_length=30, default="nucleo",
                               help_text="'nucleo' para o conjunto principal; outro rótulo (ex.: BR) para recortes comparativos.")
    file = models.FileField("arquivo", upload_to=upload_path)
    original_name = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField("sha256 do arquivo", max_length=64, blank=True, db_index=True)
    query_text = models.TextField(
        "consulta registrada (declarada)", blank=True,
        help_text="Colada pelo analista do histórico da base. Nunca preenchida a partir do arquivo de resultado.")
    query_no_arquivo = models.TextField(
        "consulta lida do arquivo", blank=True,
        help_text="Texto que a exportação imprime no cabeçalho — evidência, não registro.")
    query_no_arquivo_em = models.DateTimeField("lida do arquivo em", null=True, blank=True)
    executed_at = models.CharField("data/hora da busca", max_length=60, blank=True)
    n_records = models.PositiveIntegerField(default=0)
    uploaded = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "arquivo de exportação"
        ordering = ["recorte", "source"]

    def __str__(self):
        return f"{self.get_source_display()} [{self.recorte}] {self.original_name}"

    @property
    def consulta_extraida(self) -> bool:
        """Há texto lido do arquivo (evidência) — não confundir com consulta declarada."""
        return bool(self.query_no_arquivo.strip())


class Record(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="records")
    source_file = models.ForeignKey(SourceFile, on_delete=models.CASCADE, related_name="records")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    recorte = models.CharField(max_length=30)
    row = models.PositiveIntegerField()
    data = models.JSONField()
    excluded_utility = models.BooleanField(default=False)
    family_key = models.CharField(max_length=20, blank=True, db_index=True)

    class Meta:
        ordering = ["source", "row"]
        unique_together = [("source_file", "row")]

    @property
    def record_id(self):
        return f"{self.source}:{self.recorte}:{self.row}"


class Family(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="families")
    key = models.CharField(max_length=20)
    anchor = models.CharField(max_length=40, db_index=True)
    numbers = models.JSONField(default=list)
    fields = models.JSONField(default=dict)
    origin = models.JSONField(default=dict)
    lexical = models.JSONField(default=dict)
    n_sources = models.PositiveSmallIntegerField(default=1)
    title = models.TextField(blank=True)

    class Meta:
        verbose_name = "família consolidada"
        verbose_name_plural = "famílias consolidadas"
        ordering = ["key"]
        unique_together = [("round", "key")]

    def __str__(self):
        return f"{self.key} — {self.title[:80]}"


class ManualLink(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="manual_links")
    number_a = models.CharField("número A", max_length=40)
    number_b = models.CharField("número B", max_length=40)
    reason = models.TextField("justificativa", blank=True,
                              default="Mesma prioridade mais antiga, mesmo depositante e título equivalente; verificação manual.")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ligação manual"
        verbose_name_plural = "ligações manuais"

    def __str__(self):
        return f"{self.number_a} ↔ {self.number_b}"


class RejectedSuggestion(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="rejected_suggestions")
    number_a = models.CharField(max_length=40)
    number_b = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True)


STAGE_CHOICES = [("", "pendente"), ("incluir", "incluir"), ("excluir", "excluir")]


class Decision(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="decisions")
    anchor = models.CharField(max_length=40, db_index=True)
    numbers = models.JSONField(default=list)
    stage1 = models.CharField("etapa 1", max_length=10, choices=STAGE_CHOICES, blank=True)
    stage1_reason = models.CharField("motivo (etapa 1)", max_length=120, blank=True)
    stage2 = models.CharField("etapa 2", max_length=10, choices=STAGE_CHOICES, blank=True)
    stage2_reason = models.CharField("segmento/motivo (etapa 2)", max_length=120, blank=True)
    stratum = models.CharField("estrato", max_length=10, blank=True)
    notes = models.TextField("observações", blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "decisão de elegibilidade"
        verbose_name_plural = "decisões de elegibilidade"

    def __str__(self):
        return f"{self.anchor}: {self.stage1}/{self.stage2}/{self.stratum}"


class ApplicantAlias(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="applicant_aliases")
    raw_key = models.CharField(max_length=300)
    raw_example = models.CharField("grafia exportada", max_length=300)
    harmonized = models.CharField("nome harmonizado", max_length=300)
    group = models.CharField("grupo econômico", max_length=200, blank=True)
    is_person = models.BooleanField("pessoa física", default=False)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "harmonização de depositante"
        verbose_name_plural = "harmonização de depositantes"
        unique_together = [("study", "raw_key")]
        ordering = ["group", "harmonized"]


class InventorAlias(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="inventor_aliases")
    raw_key = models.CharField(max_length=300)
    raw_example = models.CharField("grafia exportada", max_length=300)
    standard = models.CharField("forma padronizada (sobrenome prenome)", max_length=300)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "padronização de inventor"
        verbose_name_plural = "padronização de inventores"
        unique_together = [("study", "raw_key")]


THESAURUS_CATEGORIES = [
    ("unificacao_sigla", "Unificação: sigla ou variante gráfica"),
    ("unificacao_sinonimo", "Unificação: sinônimo técnico"),
    ("unificacao_hifen", "Unificação: fragmento de hifenização"),
    ("exclusao_formula", "Exclusão: fórmula do discurso patentário"),
    ("exclusao_marcador", "Exclusão: marcador de resumo estruturado"),
    ("exclusao_generico", "Exclusão: substantivo genérico de método/artefato"),
    ("exclusao_avaliacao", "Exclusão: termo de avaliação"),
    ("exclusao_outro", "Exclusão: outro"),
]


class ThesaurusEntry(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="thesaurus")
    label = models.CharField("termo", max_length=200)
    replace_by = models.CharField("substituir por (vazio = excluir)", max_length=200, blank=True)
    category = models.CharField("categoria", max_length=30, choices=THESAURUS_CATEGORIES, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "entrada do tesauro"
        verbose_name_plural = "tesauro"
        unique_together = [("study", "label")]
        ordering = ["replace_by", "label"]


class VosRun(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="vos_runs")
    label = models.CharField("rótulo", max_length=120, default="mapa principal")
    map_file = models.FileField(upload_to="vos/")
    network_file = models.FileField(upload_to="vos/")
    params = models.TextField("parâmetros registrados", blank=True)
    cluster_labels = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
