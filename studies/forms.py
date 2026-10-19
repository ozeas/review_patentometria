import json

from django import forms

from core.records import SOURCE_LABELS

from . import models as m


class StudyForm(forms.ModelForm):
    preset = forms.ChoiceField(required=False, label="Configuração inicial",
                               choices=[("", "padrão (patentometria genérico)")])

    class Meta:
        model = m.Study
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.presets import listar_presets
        self.fields["preset"].choices = [("", "padrão (patentometria genérico)")] + \
            [(p.name, p.stem) for p in listar_presets()]


class ConfigForm(forms.Form):
    config = forms.CharField(widget=forms.Textarea(attrs={"rows": 40, "class": "mono"}),
                             label="Configuração (JSON)")

    def clean_config(self):
        try:
            data = json.loads(self.cleaned_data["config"])
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"JSON inválido: {e}")
        from core.config import normalize_config, validate_config
        erros = validate_config(data)
        if erros:
            raise forms.ValidationError(erros)
        return normalize_config(data)


class RoundForm(forms.ModelForm):
    class Meta:
        model = m.Round
        fields = ["label", "collection_date", "notes"]
        widgets = {"collection_date": forms.DateInput(attrs={"type": "date"})}


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class UploadForm(forms.Form):
    files = forms.FileField(widget=MultiFileInput(attrs={"multiple": True}), label="Arquivos de exportação")
    source = forms.ChoiceField(choices=[("", "detectar automaticamente")] + list(SOURCE_LABELS.items()),
                               required=False, label="Base")
    recorte = forms.CharField(required=False, label="Recorte",
                              help_text="Vazio: deduzido do nome do arquivo (_BR → BR; demais → nucleo).")
    executed_at = forms.CharField(required=False, label="Data/hora da busca")


class QueryForm(forms.Form):
    query_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5, "class": "mono"}), required=False,
        label="Consulta registrada (declarada)",
        help_text="Cole aqui a consulta do histórico da base. Não é lida do arquivo de resultado.")
    executed_at = forms.CharField(required=False, label="Data/hora da busca")


class VosUploadForm(forms.Form):
    label = forms.CharField(initial="mapa principal", label="Rótulo")
    map_file = forms.FileField(label="Arquivo de mapa (map.txt)")
    network_file = forms.FileField(label="Arquivo de rede (network.txt)")
    params = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), required=False,
                             label="Parâmetros registrados (versão, limiar, % relevância, normalização, resolução...)")


class ImportForm(forms.Form):
    file = forms.FileField(label="Arquivo (CSV com ';' ou ',', ou XLSX)")


class ThesaurusForm(forms.ModelForm):
    class Meta:
        model = m.ThesaurusEntry
        fields = ["label", "replace_by", "category", "note"]
