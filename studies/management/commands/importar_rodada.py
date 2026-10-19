"""Importa todas as exportações de uma pasta para uma rodada.

    python manage.py importar_rodada --estudo "GC x petróleo" --rodada "15/10/2026" \
        --data 2026-10-15 --pasta ./dados/2026-10-15

Base e recorte são deduzidos do conteúdo e do nome do arquivo
(lens_nucleo.csv, espacenet_BR.csv, darwent_nucleo.txt...). Arquivos
*_query.txt são registrados como a consulta do arquivo correspondente;
*_concepts.csv do Google Patents são ignorados.
"""
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from studies import models as m
from studies import services


class Command(BaseCommand):
    help = "Importa uma pasta de exportações para uma rodada (cria estudo e rodada se necessário)."

    def add_arguments(self, p):
        p.add_argument("--estudo", required=True)
        p.add_argument("--rodada", required=True)
        p.add_argument("--data", help="data da coleta (AAAA-MM-DD)")
        p.add_argument("--pasta", required=True)
        p.add_argument("--execucao", default="", help="data/hora da busca, ex.: '15/10/2026 16h'")
        p.add_argument("--substituir", action="store_true", help="remove arquivos já importados na rodada")

    def handle(self, *a, **o):
        folder = Path(o["pasta"])
        if not folder.is_dir():
            raise CommandError(f"Pasta não encontrada: {folder}")
        study, _ = m.Study.objects.get_or_create(name=o["estudo"])
        rnd, _ = m.Round.objects.get_or_create(study=study, label=o["rodada"])
        if o["data"]:
            rnd.collection_date = services.parse_date_or_none(o["data"])
            rnd.save()
        if o["substituir"]:
            rnd.files.all().delete()
        queries = {}
        for f in folder.iterdir():
            n = f.name.lower()
            if n.endswith("_query.txt"):
                queries[n[: -len("_query.txt")]] = f.read_text(encoding="utf-8-sig", errors="replace")
        for f in sorted(folder.iterdir()):
            n = f.name.lower()
            if not f.is_file() or n.endswith("_query.txt") or "concepts" in n or n.startswith("."):
                continue
            if f.suffix.lower() not in (".csv", ".txt", ".tsv"):
                continue
            with f.open("rb") as fh:
                try:
                    sf = services.ingest(rnd, File(fh, name=f.name), query_text=queries.get(f.stem.lower(), ""),
                                         executed_at=o["execucao"])
                except ValueError as e:
                    self.stderr.write(f"{f.name}: {e}")
                    continue
            self.stdout.write(f"{f.name}: {sf.n_records} registros ({sf.source}, {sf.recorte})")
        self.stdout.write(self.style.SUCCESS(f"Rodada {rnd.id} — {rnd}"))
