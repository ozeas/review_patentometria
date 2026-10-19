import json
import sys

from django.core.management.base import BaseCommand

from studies import models as m
from studies import services


class Command(BaseCommand):
    help = "Executa a consolidação de uma rodada e imprime o fluxo PRISMA."

    def add_arguments(self, p):
        p.add_argument("rodada", type=int)
        p.add_argument("--json", action="store_true")
        p.add_argument("--exigir-consulta", action="store_true",
                       help="falha (código 1) se alguma exportação estiver sem consulta registrada")

    def handle(self, *a, **o):
        rnd = m.Round.objects.get(pk=o["rodada"])
        result = services.run_round(rnd)
        p = result.prisma()
        prov = services.provenance(rnd)
        if o["json"]:
            self.stdout.write(json.dumps({"prisma": p, "br": services._br_summary(result),
                                          "sugestoes_ligacao": len(result.suggestions),
                                          "procedencia": prov}, ensure_ascii=False, indent=2))
        else:
            w = self.stdout.write
            w(f"Identificados ............ {p['identified']}  {p['identified_by_source']}")
            w(f"Modelos de utilidade ..... {p['excluded_utility']}  {p['excluded_utility_by_source']}")
            w(f"Elegíveis ................ {p['eligible']}")
            w(f"Famílias ................. {p['families']}  (redundantes {p['redundant']}; {p['redundant_pct']}%)")
            w(f"Famílias por nº de bases . {p['families_by_n_sources']}")
            w(f"Exclusivas por base ...... {p['exclusive_by_source']}")
            w(f"Ligações manuais ......... aplicadas {p['manual_links_applied']}; sem correspondência {p['manual_links_unmatched']}")
            w(f"Etapa 1 .................. mantidas {p['stage1_included']}; excluídas {p['stage1_excluded']} {p['stage1_excluded_by_reason']}; pendentes {p['pending_stage1']}")
            w(f"Etapa 2 .................. final {p['final']}; excluídas {p['stage2_excluded']} {p['stage2_excluded_by_reason']}; pendentes {p['pending_stage2']}")
            w(f"Estratos ................. {p['strata']}")
            if result.br:
                w(f"Recorte .................. {services._br_summary(result)}")
            w(f"Sugestões de ligação ..... {len(result.suggestions)}")
            if prov["sem_consulta"]:
                w(self.style.WARNING(f"Sem consulta declarada .. {', '.join(prov['sem_consulta'])}"))
            if prov["consulta_divergente"]:
                w(self.style.WARNING(f"DIVERGE do arquivo ...... {', '.join(prov['consulta_divergente'])}"))
            if prov["data_coleta"] is None:
                w(self.style.WARNING("Rodada sem data de coleta — a janela recente e as prioridades ficam relativas."))
        if o["exigir_consulta"] and (prov["sem_consulta"] or prov["consulta_divergente"]):
            self.stderr.write(self.style.ERROR(
                f"Consulta declarada ausente em {len(prov['sem_consulta'])} arquivo(s) e divergente "
                f"do arquivo em {len(prov['consulta_divergente'])}. "
                "Declare com `manage.py registrar_consulta` — o texto do cabeçalho é evidência, não registro."))
            sys.exit(1)
