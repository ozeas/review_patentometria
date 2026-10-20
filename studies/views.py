import json
from collections import Counter
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from core.lexical import compile_blocks, highlight
from core.normalize import normalize_pub
from core.queries import consultas_divergem
from core.records import SOURCE_LABELS, SOURCES
from core.sources import CAMPOS, matriz
from core.vosviewer import cluster_indicators, parse_map, parse_network

from . import export, forms, models as m, services, tabular


def healthz(request):
    """Prontidão para o instalador e para o CI: versão e estado do processo."""
    from importlib.metadata import PackageNotFoundError, version as _version
    from django.http import JsonResponse
    try:
        v = _version("patentometria")
    except PackageNotFoundError:
        v = "dev"
    return JsonResponse({"status": "ok", "version": v})


# ------------------------------------------------------------------ estudos
def home(request):
    if request.method == "POST":
        form = forms.StudyForm(request.POST)
        if form.is_valid():
            s = form.save(commit=False)
            escolha = form.cleaned_data.get("preset")
            if escolha:
                from core.presets import DIR_PADRAO, carregar_preset
                s.config = carregar_preset(DIR_PADRAO / escolha)
                messages.success(request, f"Estudo criado a partir do preset {escolha}.")
            else:
                messages.success(request, "Estudo criado com o padrão genérico de patentometria.")
            s.save()
            return redirect("study", s.id)
    else:
        form = forms.StudyForm()
    from core.presets import listar_presets
    return render(request, "studies/home.html", {
        "studies": m.Study.objects.all(), "form": form, "presets": listar_presets()})


def study_detail(request, pk):
    study = get_object_or_404(m.Study, pk=pk)
    if request.method == "POST":
        form = forms.RoundForm(request.POST)
        if form.is_valid():
            r = form.save(commit=False)
            r.study = study
            r.save()
            return redirect("round", r.id)
    else:
        form = forms.RoundForm()
    counts = {
        "decisoes": study.decisions.count(), "ligacoes": study.manual_links.count(),
        "depositantes": study.applicant_aliases.count(), "inventores": study.inventor_aliases.count(),
        "tesauro": study.thesaurus.count(),
    }
    return render(request, "studies/study.html", {"study": study, "form": form, "counts": counts,
                                                  "cfg": study.cfg})


def study_config(request, pk):
    study = get_object_or_404(m.Study, pk=pk)
    if request.method == "POST":
        form = forms.ConfigForm(request.POST)
        if form.is_valid():
            study.config = form.cleaned_data["config"]
            study.save()
            messages.success(request, "Configuração salva. Reexecute as rodadas para aplicá-la.")
            return redirect("study", study.id)
    else:
        form = forms.ConfigForm(initial={"config": json.dumps(study.cfg, ensure_ascii=False, indent=2)})
    return render(request, "studies/config.html", {"study": study, "form": form,
                                                   "matriz": matriz(), "campos": CAMPOS,
                                                   "labels": SOURCE_LABELS})


# ------------------------------------------------------------------ rodadas
def round_detail(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    result = services.resumo(rnd) if rnd.files.exists() else None
    prisma = result.prisma() if result else None
    return render(request, "studies/round.html", {
        "round": rnd, "study": rnd.study, "upload": forms.UploadForm(), "prisma": prisma,
        "result": result, "labels": SOURCE_LABELS, "sources": SOURCES,
        "has_families": rnd.families.exists(),
        "files": rnd.files.all(), "diag": (result.diagnostico if result else None),
    })


@require_POST
def round_upload(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    form = forms.UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Selecione ao menos um arquivo.")
        return redirect("round", pk)
    files = request.FILES.getlist("files")
    queries = {}
    data_files = []
    for f in files:
        low = f.name.lower()
        if low.endswith("_query.txt") or low.endswith("-query.txt"):
            queries[low.rsplit("_query", 1)[0].rsplit("-query", 1)[0]] = f.read().decode("utf-8-sig", "replace")
        elif "concepts" in low:
            messages.info(request, f"{f.name}: arquivo de conceitos do Google Patents ignorado.")
        else:
            data_files.append(f)
    for f in data_files:
        try:
            stem = f.name.lower().rsplit(".", 1)[0]
            sf = services.ingest(rnd, f, form.cleaned_data["source"] or None, form.cleaned_data["recorte"] or None,
                                 query_text=queries.get(stem, ""), executed_at=form.cleaned_data["executed_at"])
            messages.success(request, f"{f.name}: {sf.n_records} registros ({sf.get_source_display()}, {sf.recorte}).")
        except Exception as e:  # noqa: BLE001
            messages.error(request, f"{f.name}: {e}")
    return redirect("round", pk)


@require_POST
def file_delete(request, pk):
    sf = get_object_or_404(m.SourceFile, pk=pk)
    rid = sf.round_id
    sf.delete()
    messages.info(request, "Arquivo removido. Reexecute a consolidação.")
    return redirect("round", rid)


def file_edit(request, pk):
    sf = get_object_or_404(m.SourceFile, pk=pk)
    if request.method == "POST":
        form = forms.QueryForm(request.POST)
        if form.is_valid():
            sf.query_text = form.cleaned_data["query_text"]
            sf.executed_at = form.cleaned_data["executed_at"]
            sf.save()
            return redirect("round", sf.round_id)
    else:
        form = forms.QueryForm(initial={"query_text": sf.query_text, "executed_at": sf.executed_at})
    return render(request, "studies/file_edit.html", {
        "sf": sf, "form": form, "round": sf.round, "study": sf.round.study,
        "divergente": consultas_divergem(sf.query_text, sf.query_no_arquivo)})


@require_POST
def round_run(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    result = services.run_round(rnd)
    s = result.stats
    messages.success(request, f"Consolidação concluída: {s['identified']} registros → {s['eligible']} elegíveis → "
                              f"{s['families']} famílias.")
    return redirect("round", pk)


# ------------------------------------------------------------------ famílias
def family_list(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    qs = rnd.families.all()
    if request.GET.get("bases"):
        qs = qs.filter(n_sources=int(request.GET["bases"]))
    fams = list(qs)
    q = request.GET.get("q", "").strip()
    if q:
        num = normalize_pub(q)
        nq = num.number if num and num.country else None
        ql = q.lower()
        fams = [f for f in fams if ql in f.title.lower() or f.key.lower() == ql
                or (nq and nq in f.numbers)
                or any(ql in g.lower() for g in f.fields.get("groups", []))]
    dm = services.decisions_map(study, fams)
    status = request.GET.get("status", "")
    stratum = request.GET.get("estrato", "")

    def st(f):
        d = dm.get(f.key)
        if not d or not d.stage1:
            return "pendente1"
        if d.stage1 == "excluir":
            return "excluida1"
        if not d.stage2:
            return "pendente2"
        return "excluida2" if d.stage2 == "excluir" else "final"

    rows = [{"f": f, "d": dm.get(f.key), "status": st(f)} for f in fams]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if stratum:
        rows = [r for r in rows if r["d"] and r["d"].stratum == stratum]
    counts = Counter(st(f) for f in fams)
    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    return render(request, "studies/families.html", {
        "round": rnd, "study": study, "page": page, "counts": counts, "q": q, "status": status,
        "strata": study.cfg["strata"], "estrato": stratum, "labels": SOURCE_LABELS,
        "querystring": urlencode({k: v for k, v in request.GET.items() if k != "page"}),
    })


def _neighbors(rnd, key, study, mode):
    fams = list(rnd.families.all())
    keys = [f.key for f in fams]
    i = keys.index(key)
    nxt = keys[i + 1] if i + 1 < len(keys) else None
    prv = keys[i - 1] if i > 0 else None
    pending = None
    if mode:
        dm = services.decisions_map(study, fams)
        order = fams[i + 1:] + fams[:i]
        for f in order:
            d = dm.get(f.key)
            if mode == "1" and (not d or not d.stage1):
                pending = f.key
                break
            if mode == "2" and d and d.stage1 == "incluir" and not d.stage2:
                pending = f.key
                break
            if mode == "3" and d and d.stage1 == "incluir" and d.stage2 == "incluir" and not d.stratum:
                pending = f.key
                break
    return prv, nxt, pending


def family_detail(request, pk, key):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    fam = get_object_or_404(m.Family, round=rnd, key=key)
    cfg = study.cfg
    mode = request.GET.get("triagem", "")
    if request.method == "POST":
        action = request.POST.get("action", "decision")
        if action == "decision":
            services.save_decision(study, fam, **{k: request.POST.get(k, "") for k in (
                "stage1", "stage1_reason", "stage2", "stage2_reason", "stratum", "notes")})
            messages.success(request, f"{fam.key}: decisão registrada.")
            _, nxt, pending = _neighbors(rnd, key, study, mode)
            if request.POST.get("go") == "next" and (pending or nxt):
                url = f"/r/{rnd.id}/f/{pending or nxt}/"
                return redirect(url + (f"?triagem={mode}" if mode else ""))
        elif action == "link":
            other = normalize_pub(request.POST.get("other", ""))
            if other and other.country:
                m.ManualLink.objects.create(study=study, number_a=fam.anchor, number_b=other.number,
                                            reason=request.POST.get("reason", "") or m.ManualLink._meta.get_field("reason").default)
                messages.success(request, "Ligação manual registrada. Reexecute a consolidação para aplicá-la.")
        return redirect(request.get_full_path())
    blocks = compile_blocks(cfg.get("blocks", []))
    title = fam.fields.get("original_title") or fam.fields.get("title", "")
    hl_title = mark_safe(highlight(escape(title), blocks))
    hl_abs = mark_safe(highlight(escape(fam.fields.get("abstract", "")), blocks))
    decision = services.decision_for_family(study, fam.numbers)
    recs = rnd.records.filter(family_key=fam.key, recorte=cfg["core_recorte"])
    prv, nxt, pending = _neighbors(rnd, key, study, mode)
    return render(request, "studies/family.html", {
        "round": rnd, "study": study, "f": fam, "x": fam.fields, "o": fam.origin, "lex": fam.lexical,
        "hl_title": hl_title, "hl_abs": hl_abs, "d": decision, "cfg": cfg, "records": recs,
        "prev": prv, "next": nxt, "pending": pending, "mode": mode, "labels": SOURCE_LABELS,
    })


def triage_start(request, pk, stage):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    fams = list(rnd.families.all())
    dm = services.decisions_map(study, fams)
    for f in fams:
        d = dm.get(f.key)
        if stage == "1" and (not d or not d.stage1):
            return redirect(f"/r/{rnd.id}/f/{f.key}/?triagem=1")
        if stage == "2" and d and d.stage1 == "incluir" and not d.stage2:
            return redirect(f"/r/{rnd.id}/f/{f.key}/?triagem=2")
        if stage == "3" and d and d.stage1 == "incluir" and d.stage2 == "incluir" and not d.stratum:
            return redirect(f"/r/{rnd.id}/f/{f.key}/?triagem=3")
    messages.info(request, "Não há famílias pendentes nesta etapa.")
    return redirect("families", pk)


# ------------------------------------------------------------------ ligações
def links(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    if request.method == "POST":
        a, b = request.POST.get("number_a"), request.POST.get("number_b")
        if request.POST.get("action") == "accept":
            m.ManualLink.objects.get_or_create(study=study, number_a=a, number_b=b)
            messages.success(request, f"Ligação {a} ↔ {b} registrada.")
        elif request.POST.get("action") == "reject":
            m.RejectedSuggestion.objects.get_or_create(study=study, number_a=a, number_b=b)
        elif request.POST.get("action") == "delete":
            m.ManualLink.objects.filter(study=study, id=request.POST.get("id")).delete()
        return redirect("links", pk)
    resumo = services.resumo(rnd)
    return render(request, "studies/links.html", {
        "round": rnd, "study": study, "suggestions": resumo.ligacoes["sugestoes"],
        "links": study.manual_links.all(), "applied": set(resumo.ligacoes["aplicadas"]),
        "unmatched": set(resumo.ligacoes["sem_correspondencia"]),
    })


# ------------------------------------------------------------------ dicionários
def dict_applicants(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    if request.method == "POST":
        n = 0
        for k in request.POST:
            if k.startswith("raw_"):
                idx = k[4:]
                raw = request.POST[k]
                h = request.POST.get(f"h_{idx}", "").strip()
                g = request.POST.get(f"g_{idx}", "").strip()
                if h or g:
                    services.upsert_applicant(study, raw, h or raw, g)
                    n += 1
        messages.success(request, f"{n} grafias salvas. Reexecute a consolidação para atualizar as famílias.")
        return redirect(request.get_full_path())
    inv = services.applicant_inventory(rnd)
    filt = request.GET.get("filtro", "")
    if filt == "pendentes":
        inv = [r for r in inv if not r["alias"]]
    elif filt == "cjk":
        inv = [r for r in inv if r["cjk"]]
    q = request.GET.get("q", "").upper()
    if q:
        inv = [r for r in inv if q in r["raw"].upper() or q in (r["group"] or "").upper()]
    groups = sorted({a.group for a in study.applicant_aliases.all() if a.group})
    return render(request, "studies/dict_applicants.html", {
        "round": rnd, "study": study, "rows": inv[:400], "total": len(inv), "filtro": filt, "q": q,
        "groups": groups,
    })


def dict_inventors(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    if request.method == "POST":
        n = 0
        for k in request.POST:
            if k.startswith("raw_"):
                idx = k[4:]
                s = request.POST.get(f"s_{idx}", "").strip()
                if s and request.POST.get(f"ok_{idx}"):
                    services.upsert_inventor(study, request.POST[k], s)
                    n += 1
        messages.success(request, f"{n} nomes de inventores salvos.")
        return redirect(request.get_full_path())
    only_cjk = request.GET.get("todos") != "1"
    rows = services.inventor_inventory(rnd, only_cjk=only_cjk)
    return render(request, "studies/dict_inventors.html", {
        "round": rnd, "study": study, "rows": rows[:500], "total": len(rows), "only_cjk": only_cjk})


# ------------------------------------------------------------------ indicadores
def indicators(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    cfg = services.round_config(rnd)
    subset = request.GET.get("conjunto", "final")
    stratum = request.GET.get("estrato") or None
    data = services.indicators(rnd, subset, stratum)
    by_stratum = []
    if subset == "final":
        for s in cfg["strata"]:
            d = services.indicators(rnd, "final", s["code"])
            by_stratum.append({"s": s, "n": d["n"], "periodos": d["periodos"]["linhas"],
                               "jur": d["jurisdicao_origem"]["linhas"][:5], "grupos": d["grupos"]["linhas"][:5],
                               "ipc": d["ipc_grupos"]["linhas"][:5]})
    lex = Counter(f["fields"].get("lexical_level") for f in services._familias_db(rnd, subset))
    resumo = services.resumo(rnd)
    return render(request, "studies/indicators.html", {
        "round": rnd, "study": rnd.study, "d": data, "subset": subset, "estrato": stratum or "",
        "strata": cfg["strata"], "by_stratum": by_stratum, "prisma": resumo.prisma(),
        "lex": dict(lex), "br": resumo.br,
    })


# ------------------------------------------------------------------ VOSviewer e tesauro
def vos(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    if request.method == "POST":
        if request.POST.get("action") == "labels":
            vr = get_object_or_404(m.VosRun, pk=request.POST["run"], round=rnd)
            vr.cluster_labels = {k[6:]: v for k, v in request.POST.items() if k.startswith("label_")}
            vr.save()
            return redirect("vos", pk)
        form = forms.VosUploadForm(request.POST, request.FILES)
        if form.is_valid():
            mp = form.cleaned_data["map_file"].read().decode("utf-8-sig", "replace")
            nw = form.cleaned_data["network_file"].read().decode("utf-8-sig", "replace")
            res = cluster_indicators(parse_map(mp), parse_network(nw))
            form.cleaned_data["map_file"].seek(0)
            form.cleaned_data["network_file"].seek(0)
            m.VosRun.objects.create(round=rnd, label=form.cleaned_data["label"], map_file=form.cleaned_data["map_file"],
                                    network_file=form.cleaned_data["network_file"],
                                    params=form.cleaned_data["params"], result=res)
            messages.success(request, f"Mapa importado: {res['termos']} termos, {res['ligacoes']} ligações, "
                                      f"{len(res['clusters'])} clusters.")
            return redirect("vos", pk)
    final_n = services.contagem_final(rnd) if rnd.files.exists() else 0
    runs = rnd.vos_runs.all()
    return render(request, "studies/vos.html", {"round": rnd, "study": study, "form": forms.VosUploadForm(),
                                                "runs": runs, "final_n": final_n,
                                                "n_thes": study.thesaurus.count()})


def vos_download(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    resp = HttpResponse(export.vos_package(rnd), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="vosviewer_rodada{rnd.id}.zip"'
    return resp


def thesaurus(request, pk):
    study = get_object_or_404(m.Study, pk=pk)
    if request.method == "POST":
        if request.POST.get("action") == "import":
            f = request.FILES.get("file")
            if f:
                n = tabular.import_thesaurus(study, f.read().decode("utf-8-sig", "replace"),
                                             replace=bool(request.POST.get("replace")))
                messages.success(request, f"{n} entradas importadas.")
        elif request.POST.get("action") == "delete":
            study.thesaurus.filter(id=request.POST.get("id")).delete()
        else:
            form = forms.ThesaurusForm(request.POST)
            if form.is_valid():
                e = form.save(commit=False)
                e.study = study
                m.ThesaurusEntry.objects.update_or_create(study=study, label=e.label, defaults={
                    "replace_by": e.replace_by, "category": e.category, "note": e.note})
        return redirect("thesaurus", pk)
    entries = study.thesaurus.all()
    return render(request, "studies/thesaurus.html", {
        "study": study, "entries": entries, "form": forms.ThesaurusForm(),
        "n_unif": sum(1 for e in entries if e.replace_by), "n_excl": sum(1 for e in entries if not e.replace_by),
        "rounds": study.rounds.all()})


def thesaurus_download(request, pk):
    from core.vosviewer import build_thesaurus

    study = get_object_or_404(m.Study, pk=pk)
    txt = build_thesaurus([{"label": t.label, "replace_by": t.replace_by} for t in study.thesaurus.all()])
    resp = HttpResponse(txt, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="thesaurus.txt"'
    return resp


# ------------------------------------------------------------------ exportações e importações
def export_xlsx(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    resp = HttpResponse(export.workbook_bytes(rnd),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="base_patentometria_{rnd.study.id}_{rnd.id}.xlsx"'
    return resp


def export_decisions(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    txt = tabular.export_decisions_csv(rnd.study, list(rnd.families.all()))
    resp = HttpResponse("﻿" + txt, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="decisoes_rodada{rnd.id}.csv"'
    return resp


def import_data(request, pk):
    rnd = get_object_or_404(m.Round, pk=pk)
    study = rnd.study
    if request.method == "POST":
        kind = request.POST.get("kind")
        form = forms.ImportForm(request.POST, request.FILES)
        if form.is_valid():
            rows = tabular.read_table(form.cleaned_data["file"])
            if kind == "decisoes":
                r = tabular.import_decisions(study, rows)
                messages.success(request, f"Decisões: {r['criadas']} criadas, {r['atualizadas']} atualizadas, "
                                          f"{r['ignoradas']} linhas sem número reconhecível.")
            elif kind == "depositantes":
                messages.success(request, f"{tabular.import_applicants(study, rows)} grafias de depositantes importadas.")
            elif kind == "inventores":
                messages.success(request, f"{tabular.import_inventors(study, rows)} inventores importados.")
            elif kind == "ligacoes":
                messages.success(request, f"{tabular.import_links(study, rows)} ligações importadas.")
        return redirect("import", pk)
    return render(request, "studies/import.html", {"round": rnd, "study": study, "form": forms.ImportForm()})


def export_dict(request, pk, kind):
    study = get_object_or_404(m.Study, pk=pk)
    if kind == "depositantes":
        txt = tabular.export_table_csv(["Grafia exportada", "Nome harmonizado", "Grupo econômico"],
                                       [[a.raw_example, a.harmonized, a.group] for a in study.applicant_aliases.all()])
    elif kind == "inventores":
        txt = tabular.export_table_csv(["Grafia exportada", "Forma padronizada"],
                                       [[a.raw_example, a.standard] for a in study.inventor_aliases.all()])
    else:
        txt = tabular.export_table_csv(["Número A", "Número B", "Justificativa"],
                                       [[l.number_a, l.number_b, l.reason] for l in study.manual_links.all()])
    resp = HttpResponse("﻿" + txt, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{kind}_estudo{study.id}.csv"'
    return resp
