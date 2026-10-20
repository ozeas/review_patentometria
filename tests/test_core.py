"""Testes do núcleo do pipeline (sem Django): `python -m pytest tests` ou
`python manage.py test` (também executados pela suíte do Django)."""
from datetime import date
from pathlib import Path
from unittest import TestCase

from core import indicators as ind
from core.consolidate import ManualLink, consolidate
from core.lexical import compile_blocks, lexical_profile
from core.normalize import normalize_ipc, normalize_priority, normalize_pub, pinyin_name, token_key
from core.parsers import PARSERS, detect_source, parse_bytes
from core.pipeline import Decision, run
from core.prevalence import Dictionaries, months_before
from core.vosviewer import build_thesaurus, cluster_indicators, parse_map, parse_network

FIX = Path(__file__).parent / "fixtures"


def load_all(recorte="nucleo"):
    recs = []
    for name in ("lens_sample.csv", "espacenet_sample.csv", "google_sample.csv", "derwent_sample.txt"):
        _, r = parse_bytes((FIX / name).read_bytes(), None, recorte)
        recs.extend(r)
    return recs


class NormalizeTests(TestCase):
    def test_examples_from_methods(self):
        self.assertEqual(normalize_pub("WO 1999/058951 A1").number, "WO1999058951")
        self.assertEqual(normalize_pub("WO9958951-A1").number, "WO1999058951")
        self.assertEqual(normalize_pub("US 2010/0018287 A1").number, "US2010018287")
        self.assertEqual(normalize_pub("US2010018287A1").number, "US2010018287")
        self.assertEqual(normalize_pub("CN101413931A").number, normalize_pub("CN101413931B").number)
        self.assertEqual(normalize_pub("EP92975-A").number, "EP0092975")
        self.assertEqual(normalize_pub("US20240418698A1").number, normalize_pub("US2024418698A1").number)
        self.assertEqual(normalize_pub("US 12748097 B2").number, "US12748097")
        self.assertEqual(normalize_pub("CN205720124U").kind, "U")
        self.assertEqual(normalize_pub("BR-112019027015-A2").number, "BR112019027015")

    def test_priority_pct_receiving_office(self):
        self.assertEqual(normalize_priority("WOUS044396").country, "US")
        self.assertEqual(normalize_priority("CN 2025078734 W").country, "CN")
        self.assertEqual(normalize_priority("US 201615286225 A").number, "US201615286225")

    def test_ipc(self):
        self.assertEqual(normalize_ipc("G01N30/64"), "G01N 30/64")
        self.assertEqual(normalize_ipc("G01N-030/64"), "G01N 30/64")
        self.assertEqual(normalize_ipc("E21B49/10 (EP,US)"), "E21B 49/10")
        self.assertEqual(normalize_ipc("G01N30/78, G01N30/68, ADD (EP,US)"), "G01N 30/78")

    def test_names(self):
        self.assertEqual(token_key("ZHANG JUHE"), token_key("JUHE ZHANG"))
        self.assertEqual(pinyin_name("张居和"), "ZHANG JUHE")

    def test_months_before(self):
        self.assertEqual(months_before(date(2026, 10, 15), 36), date(2023, 10, 15))


class ParserTests(TestCase):
    def test_detect(self):
        for name, src in (("lens_sample.csv", "lens"), ("espacenet_sample.csv", "espacenet"),
                          ("google_sample.csv", "google"), ("derwent_sample.txt", "derwent")):
            self.assertEqual(detect_source((FIX / name).read_text(encoding="utf-8")), src)

    def test_espacenet_multiline(self):
        recs = PARSERS["espacenet"]((FIX / "espacenet_sample.csv").read_text(encoding="utf-8"), "nucleo")
        self.assertEqual(len(recs), 4)
        self.assertEqual(recs[1].pub_numbers, ["CN101413931"])
        self.assertEqual(recs[1].applicants, ["ACME SENSORS LTD"])
        self.assertEqual(recs[3].cpc, ["G01N 33/24", "G01N 27/04"])
        self.assertTrue(recs[2].is_utility_model_only())

    def test_derwent_cr_separator_and_sections(self):
        text = (FIX / "derwent_sample.txt").read_text(encoding="utf-8")
        cr = text.replace("\n", "\r", text.count("\n"))
        cr = cr.replace("\r", "\r\n", 1)  # cabeçalho com CRLF, registros com CR
        recs = PARSERS["derwent"](cr, "nucleo")
        self.assertEqual(len(recs), 4)
        r = recs[1]
        self.assertIn("vapor phase", r.dwpi_novelty)
        self.assertTrue(r.dwpi_use.startswith("The method"))
        self.assertEqual(r.applicants, ["GREENFIELD ANALYTICS INC"])
        self.assertIn("US2010018287", r.cited_patents)
        self.assertEqual(r.earliest_priority, date(2010, 7, 19))

    def test_google_names(self):
        recs = PARSERS["google"]((FIX / "google_sample.csv").read_text(encoding="utf-8"), "nucleo")
        self.assertEqual(recs[1].applicants, ["NORTHWIND SENSORS CORP"])
        self.assertEqual(recs[0].inventors, ["王小明", "李华", "张伟"])


class ConsolidationTests(TestCase):
    def test_counts(self):
        res = consolidate(load_all())
        s = res.stats()
        self.assertEqual(s["identified"], 15)
        self.assertEqual(s["excluded_utility"], 2)
        self.assertEqual(s["excluded_utility_by_source"],
                         {"lens": 0, "espacenet": 1, "google": 0, "derwent": 1, "inpi": 0})
        self.assertEqual(s["eligible"], 13)
        self.assertEqual(s["families"], 5)
        self.assertEqual(s["redundant"], 8)
        self.assertEqual(s["exclusive_by_source"]["derwent"], 1)
        self.assertEqual(s["exclusive_by_source"]["google"], 1)

    def test_manual_link(self):
        ml = ManualLink(1, "US2016168990", "US2012011919", "teste")
        res = consolidate(load_all(), manual_links=[ml])
        self.assertEqual(res.stats()["families"], 4)
        self.assertEqual(res.stats()["manual_links_applied"], 1)
        bad = ManualLink(2, "US0000000", "US2012011919")
        self.assertEqual(consolidate(load_all(), manual_links=[bad]).stats()["manual_links_unmatched"], 1)


class PipelineTests(TestCase):
    def test_fields_prevalence_and_decisions(self):
        dic = Dictionaries(applicants={"宏达传感器有限公司": ("ACME SENSORS LTD", "ACME")})
        dec = [Decision(numbers=["CN101413931"], stage1="incluir", stage2="incluir",
                        stage2_reason="Segmento incluído", stratum="S1"),
               Decision(numbers=["WO1999058951"], stage1="incluir", stage2="excluir",
                        stage2_reason="Segmento excluído"),
               Decision(numbers=["US2016168990"], stage1="excluir", stage1_reason="Falso positivo lexical")]
        result = run(load_all() + load_all("BR")[:0], dictionaries=dic, decisions=dec)
        fams = {f["fields"]["publications"][0]: f for f in result.families}
        cn = next(f for f in result.families if "CN101413931" in f["fields"]["all_numbers"])
        self.assertEqual(cn["origin"]["title"], "lens")
        self.assertEqual(cn["fields"]["abstract_kind"], "original")
        self.assertEqual(cn["origin"]["ipc"], "espacenet")
        self.assertEqual(cn["fields"]["origin_jurisdiction"], "CN")
        self.assertEqual(cn["fields"]["legal_status"], "vigente")
        sch = next(f for f in result.families if "US2010018287" in f["fields"]["all_numbers"])
        self.assertEqual(sch["origin"]["publications"], "derwent")
        self.assertEqual(sch["fields"]["origin_jurisdiction"], "RU")
        self.assertEqual(sch["fields"]["cited_by_max"], 24)
        self.assertEqual(sch["fields"]["legal_status"], "inativa")
        sgs = next(f for f in result.families if "US2012011919" in f["fields"]["all_numbers"])
        self.assertEqual(sgs["fields"]["abstract_kind"], "DWPI")
        self.assertEqual(sgs["fields"]["origin_jurisdiction"], "US")
        p = result.prisma()
        self.assertEqual(p["families"], 5)
        self.assertEqual(p["stage1_excluded"], 1)
        self.assertEqual(p["stage2_excluded"], 1)
        self.assertEqual(p["final"], 1)
        self.assertEqual(p["strata"]["S1"], 1)
        indicators = result.indicators("unificada")
        self.assertEqual(indicators["rede_citacoes_internas"]["arestas"], 2)
        self.assertIsNotNone(fams)

    def test_br_subset(self):
        result = run(load_all() + load_all("BR"))
        self.assertEqual(result.br["in_core"], len(result.br["families"]))


class IndicatorTests(TestCase):
    def test_concentration(self):
        c = ind.concentration([5, 3, 1, 1])
        self.assertEqual(c["CR4"], 100.0)
        self.assertEqual(c["HHI"], 3600.0)
        self.assertAlmostEqual(c["Gini"], 0.35, places=2)

    def test_lexical(self):
        blocks = compile_blocks([{"name": "a", "terms": ["optical sensor*"]},
                                 {"name": "b", "terms": ["soil sample", "field site"]}])
        self.assertEqual(lexical_profile("Field site optical sensor", "", blocks)["level"], "titulo")
        self.assertEqual(lexical_profile("OS device", "optical sensor of soil-sample", blocks)["level"],
                         "titulo+resumo")


class VosTests(TestCase):
    def test_thesaurus_order_and_clusters(self):
        th = build_thesaurus([{"label": "sensor-ms", "replace_by": "sensor ms"}, {"label": "method", "replace_by": ""}])
        self.assertTrue(th.strip().splitlines()[-1].endswith("sensor ms"))
        mp = parse_map("id\tlabel\tx\ty\tcluster\tweight<Occurrences>\tscore<Ano de prioridade>\n"
                       "1\ta\t0\t0\t1\t4\t2010\n2\tb\t0\t0\t1\t2\t2016\n3\tc\t0\t0\t2\t3\t2020\n")
        net = parse_network("1\t2\t3\n2\t3\t1\n")
        ci = cluster_indicators(mp, net)
        c1 = ci["clusters"][0]
        self.assertEqual(c1["termos"], 2)
        self.assertEqual(c1["coesao"], 0.75)
        self.assertEqual(c1["score<Ano de prioridade>"], 2012.0)
