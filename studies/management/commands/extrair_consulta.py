"""Lê a consulta do cabeçalho das exportações para o campo de evidência.

    python manage.py extrair_consulta 1 [--forcar]

Nunca escreve ``query_text``: a consulta registrada é a **declarada** pelo
analista. Este comando só registra o que a própria exportação imprime, para
comparação e auditoria.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.queries import consulta_do_arquivo, consultas_divergem
from studies import models as m


class Command(BaseCommand):
    help = "Extrai a consulta do cabeçalho das exportações para o campo de evidência."

    def add_arguments(self, p):
        p.add_argument("rodada", type=int)
        p.add_argument("--forcar", action="store_true", help="sobrescreve o que já foi lido antes")

    def handle(self, *a, **o):
        rnd = m.Round.objects.get(pk=o["rodada"])
        for sf in rnd.files.all().order_by("recorte", "source"):
            if sf.query_no_arquivo and not o["forcar"]:
                self.stdout.write(f"  {sf.original_name}: já lido, mantido")
                continue
            texto = consulta_do_arquivo(sf.source, sf.file.read().decode("utf-8-sig", errors="replace"))
            sf.file.seek(0)
            if not texto:
                self.stdout.write(self.style.WARNING(
                    f"  {sf.original_name}: a exportação não traz consulta no cabeçalho"))
                continue
            sf.query_no_arquivo = texto
            sf.query_no_arquivo_em = timezone.now()
            sf.save(update_fields=["query_no_arquivo", "query_no_arquivo_em"])
            aviso = " (DIVERGE da declarada)" if consultas_divergem(sf.query_text, texto) else ""
            self.stdout.write(f"  {sf.original_name}: consulta lida ({len(texto)} caracteres){aviso}")
        total = rnd.files.count()
        declarada = rnd.files.exclude(query_text="").count()
        evidencia = rnd.files.exclude(query_no_arquivo="").count()
        self.stdout.write(self.style.SUCCESS(
            f"Rodada {rnd.id}: consulta declarada em {declarada} de {total} arquivo(s); "
            f"evidência lida do arquivo em {evidencia}."))
