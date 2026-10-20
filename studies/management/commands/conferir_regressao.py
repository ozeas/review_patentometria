"""Confere os números de uma rodada contra valores de referência (JSON).

    python manage.py conferir_regressao 1 referencia.json

O JSON usa as mesmas chaves do fluxo PRISMA (ver ``executar_rodada --json``);
só as chaves presentes são conferidas. Sai com código 1 quando há divergência,
de modo que serve de porteiro (script, ``&&``, CI) e não só de relatório.

Com ``--exigir-procedencia`` a conferência também falha quando alguma
exportação da rodada está sem consulta registrada, sem hash ou sem data de
execução — é o que impede o número de voltar a depender de arquivo sem rastro.
"""
import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from studies import models as m
from studies import services


def _flatten(d, prefix=""):
    for k, v in d.items():
        if str(k).startswith("_"):
            continue
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            yield from _flatten(v, key + ".")
        else:
            yield key, v


class Command(BaseCommand):
    help = "Compara o fluxo PRISMA de uma rodada com uma referência (código 1 se divergir)."

    def add_arguments(self, p):
        p.add_argument("rodada", type=int)
        p.add_argument("referencia")
        p.add_argument("--exigir-procedencia", action="store_true",
                       help="falha também se houver exportação sem consulta, hash ou data de execução")

    def handle(self, *a, **o):
        rnd = m.Round.objects.get(pk=o["rodada"])
        ref = json.loads(Path(o["referencia"]).read_text(encoding="utf-8"))
        result = services.compute(rnd)
        got = {"prisma": result.prisma(), "br": services._br_summary(result) or {}}
        got_flat = dict(_flatten(got))
        ok = fail = 0
        for k, v in _flatten(ref):
            g = got_flat.get(k)
            if str(g) == str(v):
                ok += 1
                self.stdout.write(f"  ok    {k} = {v}")
            else:
                fail += 1
                self.stdout.write(self.style.ERROR(f"  DIFF  {k}: esperado {v}, obtido {g}"))

        prov = services.provenance(rnd)
        pend = []
        for chave, rotulo in (("sem_consulta", "sem consulta registrada"),
                              ("sem_hash", "sem sha256"),
                              ("sem_data_execucao", "sem data/hora da busca")):
            if prov[chave]:
                pend.append(f"{rotulo}: {', '.join(prov[chave])}")
        if not prov["data_coleta"]:
            pend.append("rodada sem data de coleta")
        if pend:
            estilo = self.style.ERROR if o["exigir_procedencia"] else self.style.WARNING
            self.stdout.write(estilo("Procedência incompleta na rodada:"))
            for linha in pend:
                self.stdout.write(estilo(f"  - {linha}"))
            if o["exigir_procedencia"]:
                fail += 1

        if prov["consulta_divergente"]:
            estilo = self.style.ERROR if o["exigir_procedencia"] else self.style.WARNING
            self.stdout.write(estilo(
                "Consulta declarada diverge do que o arquivo imprime: "
                + ", ".join(prov["consulta_divergente"])))
            if o["exigir_procedencia"]:
                fail += 1

        msg = f"{ok} conferidos, {fail} divergentes"
        self.stdout.write(self.style.SUCCESS(msg) if not fail else self.style.ERROR(msg))
        if fail:
            sys.exit(1)
