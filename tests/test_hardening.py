"""Testes das garantias de procedência e dos porteiros de regressão.

Cobrem o que foi endurecido depois da primeira entrega:
hash de cada exportação, registro de consulta obrigatório, código de saída da
conferência de regressão e o backup JSON do trabalho manual.
"""
import hashlib
import io
import json
import tempfile
from datetime import date
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from studies import models as m, services

FIX = Path(__file__).parent / "fixtures"


class ProvenanceTests(TestCase):
    def setUp(self):
        self.study = m.Study.objects.create(name="Procedência")
        self.rnd = m.Round.objects.create(study=self.study, label="r1", collection_date=date(2026, 10, 15))

    def test_sha256_registrado_do_conteudo(self):
        raw = (FIX / "lens_sample.csv").read_bytes()
        sf = services.ingest(self.rnd, SimpleUploadedFile("lens_nucleo.csv", raw),
                             query_text="G01N30 AND oil", executed_at="15/10/2026 16h")
        self.assertEqual(sf.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(sf.sha256), 64)

    def test_provenance_aponta_o_que_falta(self):
        services.ingest(self.rnd, SimpleUploadedFile("lens_nucleo.csv", (FIX / "lens_sample.csv").read_bytes()),
                        query_text="", executed_at="")
        prov = services.provenance(self.rnd)
        self.assertEqual(prov["n_arquivos"], 1)
        self.assertEqual(prov["sem_consulta"], ["lens_nucleo.csv"])
        self.assertEqual(prov["sem_data_execucao"], ["lens_nucleo.csv"])
        self.assertEqual(prov["sem_hash"], [])
        self.assertEqual(prov["data_coleta"], "2026-10-15")

    def test_run_round_guarda_procedencia_no_resumo(self):
        services.ingest(self.rnd, SimpleUploadedFile("lens_nucleo.csv", (FIX / "lens_sample.csv").read_bytes()))
        services.run_round(self.rnd)
        self.rnd.refresh_from_db()
        self.assertIn("procedencia", self.rnd.run_summary)
        self.assertEqual(self.rnd.run_summary["procedencia"]["sem_consulta"], ["lens_nucleo.csv"])

    def test_executar_rodada_exige_consulta_quando_pedido(self):
        services.ingest(self.rnd, SimpleUploadedFile("lens_nucleo.csv", (FIX / "lens_sample.csv").read_bytes()))
        # sem a flag, roda normalmente
        call_command("executar_rodada", self.rnd.id, stdout=io.StringIO())
        with self.assertRaises(SystemExit) as ctx:
            call_command("executar_rodada", self.rnd.id, exigir_consulta=True, stdout=io.StringIO())
        self.assertEqual(ctx.exception.code, 1)
        # com a consulta registrada, passa
        self.rnd.files.update(query_text="G01N30 AND oil")
        call_command("executar_rodada", self.rnd.id, exigir_consulta=True, stdout=io.StringIO())


class RegressaoGateTests(TestCase):
    def setUp(self):
        self.study = m.Study.objects.create(name="Gate")
        self.rnd = m.Round.objects.create(study=self.study, label="r1", collection_date=date(2026, 10, 15))
        for name in ("lens_sample.csv", "espacenet_sample.csv", "google_sample.csv", "derwent_sample.txt"):
            services.ingest(self.rnd, SimpleUploadedFile(name, (FIX / name).read_bytes()),
                            query_text="consulta", executed_at="15/10/2026 16h")
        prisma = services.compute(self.rnd).prisma()
        self.tmp = Path(tempfile.mkdtemp())
        self.ref_ok = self.tmp / "ok.json"
        self.ref_ok.write_text(json.dumps({"prisma": {k: prisma[k] for k in
                                                      ("identified", "excluded_utility", "eligible", "families")}}))
        self.ref_ruim = self.tmp / "ruim.json"
        self.ref_ruim.write_text(json.dumps({"prisma": {"identified": 669, "eligible": 655}}))

    def test_referencia_que_bate_passa(self):
        out = io.StringIO()
        call_command("conferir_regressao", self.rnd.id, str(self.ref_ok), stdout=out)
        self.assertIn("0 divergentes", out.getvalue())

    def test_referencia_divergente_sai_com_codigo_1(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command("conferir_regressao", self.rnd.id, str(self.ref_ruim), stdout=out)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("DIFF", out.getvalue())

    def test_exigir_procedencia_falha_sem_consulta(self):
        self.rnd.files.filter(source="lens").update(query_text="")
        out = io.StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command("conferir_regressao", self.rnd.id, str(self.ref_ok),
                         exigir_procedencia=True, stdout=out)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("sem consulta registrada", out.getvalue())


class BackupDoTrabalhoTests(TestCase):
    """O trabalho manual (decisões, ligações, dicionários, tesauro) sobrevive
    a um exportar → importar em outro estudo."""

    def setUp(self):
        self.study = m.Study.objects.create(name="Original")
        self.rnd = m.Round.objects.create(study=self.study, label="r1", collection_date=date(2026, 10, 15))
        for name in ("lens_sample.csv", "espacenet_sample.csv", "google_sample.csv", "derwent_sample.txt"):
            services.ingest(self.rnd, SimpleUploadedFile(name, (FIX / name).read_bytes()),
                            query_text="consulta", executed_at="15/10/2026 16h")
        services.run_round(self.rnd)
        fam = self.rnd.families.get(anchor="CN101413931")
        services.save_decision(self.study, fam, stage1="incluir", stage2="incluir",
                               stage2_reason="Exploração", stratum="C1")
        m.ManualLink.objects.create(study=self.study, number_a="CN101413931", number_b="US2010012345",
                                    reason="mesma prioridade")
        services.upsert_applicant(self.study, "大庆油田有限责任公司", "DAQING OILFIELD CO LTD", "CNPC")
        services.upsert_inventor(self.study, "张三", "ZHANG SAN")
        m.ThesaurusEntry.objects.create(study=self.study, label="gas chromatograph", replace_by="gas chromatography")
        self.tmp = Path(tempfile.mkdtemp())
        self.json = self.tmp / "estudo.json"

    def _exportar(self):
        call_command("exportar_estudo", self.study.id, saida=str(self.json), stdout=io.StringIO())
        return json.loads(self.json.read_text(encoding="utf-8"))

    def test_exporta_tudo_o_que_importa(self):
        payload = self._exportar()
        self.assertEqual(payload["formato"], "patentometria/estudo/1")
        self.assertEqual(len(payload["decisoes"]), 1)
        self.assertEqual(len(payload["ligacoes"]), 1)
        self.assertEqual(len(payload["depositantes"]), 1)
        self.assertEqual(len(payload["inventores"]), 1)
        self.assertEqual(len(payload["tesauro"]), 1)
        self.assertEqual(len(payload["rodadas"]), 1)
        self.assertEqual(payload["rodadas"][0]["procedencia"]["sem_consulta"], [])
        self.assertEqual(payload["estudo"]["config"]["blocks"][0]["name"], "(i) cromatografia gasosa")

    def test_restaura_em_outro_estudo(self):
        self._exportar()
        novo = m.Study.objects.create(name="Restaurado")
        call_command("importar_estudo", str(self.json), estudo=novo.id, stdout=io.StringIO())
        self.assertEqual(novo.decisions.count(), 1)
        self.assertEqual(novo.manual_links.count(), 1)
        self.assertEqual(novo.applicant_aliases.count(), 1)
        self.assertEqual(novo.inventor_aliases.count(), 1)
        self.assertEqual(novo.thesaurus.count(), 1)
        d = novo.decisions.get()
        self.assertEqual((d.stage1, d.stage2, d.stratum), ("incluir", "incluir", "C1"))
        # e a decisão restaurada vale para uma rodada nova do estudo restaurado
        rnd2 = m.Round.objects.create(study=novo, label="r2", collection_date=date(2026, 10, 15))
        for name in ("lens_sample.csv", "espacenet_sample.csv", "google_sample.csv", "derwent_sample.txt"):
            services.ingest(rnd2, SimpleUploadedFile(name, (FIX / name).read_bytes()))
        self.assertEqual(services.compute(rnd2).prisma()["final"], 1)

    def test_reimportar_nao_duplica(self):
        self._exportar()
        call_command("importar_estudo", str(self.json), estudo=self.study.id, stdout=io.StringIO())
        call_command("importar_estudo", str(self.json), estudo=self.study.id, stdout=io.StringIO())
        self.assertEqual(self.study.decisions.count(), 1)
        self.assertEqual(self.study.manual_links.count(), 1)
        self.assertEqual(self.study.thesaurus.count(), 1)

    def test_reimportar_com_renomear_nao_cria_estudo_novo(self):
        """--renomear procurado pelo nome novo: duas execuções, um estudo."""
        self._exportar()
        for _ in range(2):
            call_command("importar_estudo", str(self.json), renomear="Restaurado", stdout=io.StringIO())
        self.assertEqual(m.Study.objects.filter(name="Restaurado").count(), 1)

    def test_substituir_limpa_antes(self):
        self._exportar()
        m.ManualLink.objects.create(study=self.study, number_a="XX1", number_b="YY2")
        call_command("importar_estudo", str(self.json), estudo=self.study.id,
                     substituir=True, stdout=io.StringIO())
        self.assertEqual(self.study.manual_links.count(), 1)
        self.assertEqual(self.study.manual_links.get().number_a, "CN101413931")


class ConsultaSeparadaTests(TestCase):
    """A consulta registrada é declarada; o texto do arquivo é evidência."""

    def setUp(self):
        self.study = m.Study.objects.create(name="Consulta")
        self.rnd = m.Round.objects.create(study=self.study, label="r1", collection_date=date(2026, 10, 15))

    def test_ingestao_nao_le_consulta_do_arquivo(self):
        raw = (FIX / "espacenet_sample.csv").read_bytes()
        sf = services.ingest(self.rnd, SimpleUploadedFile("espacenet_nucleo.csv", raw))
        self.assertEqual(sf.query_text, "")
        self.assertEqual(sf.query_no_arquivo, "")

    def test_campos_de_consulta_sao_independentes(self):
        sf = services.ingest(self.rnd, SimpleUploadedFile("lens_nucleo.csv",
                                                          (FIX / "lens_sample.csv").read_bytes()))
        sf.query_text = "G01N30 AND oil"
        sf.query_no_arquivo = '(ipc =/low "G01N" OR ipc =/low "C10G")'
        sf.save()
        sf.refresh_from_db()
        self.assertEqual(sf.query_text, "G01N30 AND oil")
        self.assertEqual(sf.query_no_arquivo, '(ipc =/low "G01N" OR ipc =/low "C10G")')
        self.assertTrue(sf.consulta_extraida)

    def test_comando_extrai_so_para_o_campo_de_evidencia(self):
        cabecalho = ('"Espacenet";"";\n"Patent search";"";\n'
                     '"156 results found for (ta = ""gas chromatography"")";"";\n'
                     '"No";"Title";"Publication number"\n'
                     '"1";"T";"US1"\n')
        sf = services.ingest(self.rnd, SimpleUploadedFile("espacenet_nucleo.csv",
                                                          (FIX / "espacenet_sample.csv").read_bytes()))
        # o fixture não traz a linha da consulta; forjamos o cabeçalho no arquivo salvo
        sf.file.save("espacenet_manual.csv", ContentFile(cabecalho.encode()), save=True)

        call_command("extrair_consulta", self.rnd.id, stdout=io.StringIO())

        sf.refresh_from_db()
        self.assertEqual(sf.query_text, "")                        # declarada continua vazia
        self.assertIn("gas chromatography", sf.query_no_arquivo)    # evidência gravada
        self.assertIsNotNone(sf.query_no_arquivo_em)
