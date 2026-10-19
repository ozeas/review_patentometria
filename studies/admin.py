from django.contrib import admin

from . import models as m


@admin.register(m.Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ("name", "created")


@admin.register(m.Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("label", "study", "collection_date", "last_run")


@admin.register(m.SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    list_display = ("original_name", "source", "recorte", "n_records", "round")
    list_filter = ("source", "recorte")


@admin.register(m.Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ("anchor", "stage1", "stage1_reason", "stage2", "stage2_reason", "stratum", "updated")
    list_filter = ("stage1", "stage2", "stratum")
    search_fields = ("anchor", "notes")


@admin.register(m.ApplicantAlias)
class ApplicantAliasAdmin(admin.ModelAdmin):
    list_display = ("raw_example", "harmonized", "group", "is_person")
    search_fields = ("raw_example", "harmonized", "group")
    list_filter = ("study",)


@admin.register(m.InventorAlias)
class InventorAliasAdmin(admin.ModelAdmin):
    list_display = ("raw_example", "standard")
    search_fields = ("raw_example", "standard")


@admin.register(m.ManualLink)
class ManualLinkAdmin(admin.ModelAdmin):
    list_display = ("number_a", "number_b", "reason", "created")


@admin.register(m.ThesaurusEntry)
class ThesaurusAdmin(admin.ModelAdmin):
    list_display = ("label", "replace_by", "category")
    list_filter = ("category",)
    search_fields = ("label", "replace_by")


admin.site.register(m.VosRun)
admin.site.register(m.Family)
admin.site.site_header = "Patentometria — administração"
