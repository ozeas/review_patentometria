"""Cache do pipeline por rodada, invalidado por hash de todos os insumos."""
from datetime import date
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from studies import models as m, services

FIX = Path(__file__).parent / "fixtures"
NOMES = ("lens_sample.csv", "espacenet_sample.csv", "google_sample.csv", "derwent_sample.txt")


class CacheTests(TestCase):
    def setUp(self):
        self.study = m.Study.objects.create(name="Cache")
        self.rnd = m.Round.objects.create(study=self.study, label="r1", collection_date=date(2026, 10, 15))
        for nome in NOMES:
            services.ingest(self.rnd, SimpleUploadedFile(nome, (FIX / nome).read_bytes()))

    def _espiao(self):
        """Conta chamadas a compute() sem mudar o comportamento."""
        chamadas = []
        original = services.compute
        services.compute = lambda r: chamadas.append(r) or original(r)
        self.addCleanup(setattr, services, "compute", original)
        return chamadas

    def test_segunda_leitura_usa_cache(self):
        p1 = services.resumo(self.rnd).prisma()
        espiao = self._espiao()
        p2 = services.resumo(self.rnd).prisma()
        self.assertEqual(espiao, [])                      # não recalculou
        self.assertEqual(p1["families"], p2["families"])
        self.assertEqual(p1["identified"], p2["identified"])

    def test_decisao_invalida_o_cache(self):
        services.resumo(self.rnd)
        fam = self.rnd.families.first()
        espiao = self._espiao()
        services.save_decision(self.study, fam, stage1="incluir", stage2="incluir", stratum="C1")
        services.resumo(self.rnd)
        self.assertEqual(len(espiao), 1)                  # refez uma vez

    def test_novo_arquivo_invalida_o_cache(self):
        services.resumo(self.rnd)
        espiao = self._espiao()
        services.ingest(self.rnd, SimpleUploadedFile("lens_BR.csv", (FIX / "lens_sample.csv").read_bytes()))
        services.resumo(self.rnd)
        self.assertEqual(len(espiao), 1)

    def test_indicadores_saem_das_familias_gravadas(self):
        services.resumo(self.rnd)
        fam = self.rnd.families.first()
        services.save_decision(self.study, fam, stage1="incluir", stage2="incluir", stratum="C1")
        espiao = self._espiao()
        d = services.indicators(self.rnd, "final")
        self.assertEqual(d["n"], 1)
        self.assertEqual(espiao, [])                      # indicadores não rodam o pipeline
        self.assertEqual(services.contagem_final(self.rnd), 1)
