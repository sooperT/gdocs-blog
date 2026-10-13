#!/usr/bin/env python3
"""Tests for scripts/send_outcomes.py: stubbed rows, no network, no database.

    python3 scripts/test_send_outcomes.py
"""

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import send_outcomes as so  # noqa: E402

TODAY = date(2026, 10, 20)
T0 = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)
SECRET_QUESTION = "what did Tom do at Novo Nordisk in 2023"
LONG_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 " + "x" * 80
VISITOR_UA = "weird-agent/1.0 ip=203.0.113.9 q=" + SECRET_QUESTION + " " + "y" * 100


def row(path, ua, days=0, meta=None, referer=None, status=200):
    return dict(created_at=T0 + timedelta(days=days), path=path, user_agent=ua, referer=referer, status=status, meta=meta)


SENDS_JSON = {"sends": {
    "novonesis": {"role": "Senior Principal Innovation PM", "company": "Novonesis", "fit": "/for-agents/fit/novonesis/",
                  "jd": "x", "date": "2026-10-12", "answers": {"location": "onsite: yes"}},
    "acme-pm": {"role": "Head of Product", "company": "Acme", "date": "2026-10-01"},
    "nofetch": {"role": "PM", "company": "Quiet Co", "date": "2026-10-05"},
    "stale": {"role": "PM", "company": "Stale Ltd", "date": "2026-09-01"},
}}

STUB_ROWS = [
    # acme-pm: a ChatGPT fetch of the HTML entry page on day 2, a Claude fetch of the .md on day 3, one probe, two asks, one brief
    row("/for-agents/start/acme-pm/", "ChatGPT-User/1.0", days=-10, meta={"tag": "acme-pm"}),            # 2026-10-03
    row("/for-agents/start/acme-pm.md", "Mozilla/5.0 (compatible; ClaudeBot/1.0)", days=-9, meta={"tag": "acme-pm"}),
    row("/for-agents/start/acme-pm/", "tbn-check-staging/1.0", days=-8, meta={"tag": "acme-pm"}),
    row("/ask", "ChatGPT-User/1.0", days=-9, meta={"tag": "acme-pm", "asker": "recruiter-agent", "section": "FIT.TEAM"}),
    row("/ask", "ChatGPT-User/1.0", days=-9, meta={"tag": "acme-pm", "asker": SECRET_QUESTION, "section": None}),
    row("/ask/brief", "ChatGPT-User/1.0", days=-9, meta={"tag": "acme-pm", "requirements": 5, "met": 2}),
    # novonesis: path only, no meta (a row from before the meta column), a visitor-controlled user agent with an IP
    row("/for-agents/start/novonesis/", VISITOR_UA, days=1, referer="https://claude.ai/chat?q=" + SECRET_QUESTION),
    row("/for-agents/start/novonesis.md", LONG_UA, days=2),
    # stale: only an internal probe
    row("/for-agents/start/stale/", "curl/8.7.1", days=0, meta={"tag": "stale"}),
    # a tag nobody registered, and untagged traffic
    row("/for-agents/start/ghost-tag/", "ChatGPT-User/1.0", days=0, meta={"tag": "ghost-tag"}),
    row("/for-agents/", "Mozilla/5.0 (compatible; GPTBot/1.1)", days=0),
    row("/for-agents/start/", "ChatGPT-User/1.0", days=0),
    row("/ask", "Claude-User/1.0", days=0, meta={"tag": None, "section": "META"}),
]

PIPELINE = [
    {"company": "Acme", "role": "Head of Product", "stage": "Active", "outcome": "", "reply": "2026-10-06", "interview": "2026-10-15", "tag": ""},
    {"company": "novonesis", "role": "Senior Principal Innovation PM", "stage": "Active", "outcome": "", "reply": "", "interview": "", "tag": ""},
    {"company": "Quiet Co", "role": "PM", "stage": "Active", "outcome": "", "reply": "2026-10-09", "interview": "", "tag": ""},
    {"company": "Somebody Else", "role": "PM", "stage": "Dead", "outcome": "Rejected", "reply": "", "interview": "", "tag": "stale"},
]


class SendsRegister(unittest.TestCase):
    def test_parse(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sends.json")
            with open(p, "w") as fh:
                json.dump(SENDS_JSON, fh)
            sends = so.load_sends(p)
        self.assertEqual([s["tag"] for s in sends], ["stale", "acme-pm", "nofetch", "novonesis"])  # oldest first
        nov = sends[-1]
        self.assertEqual((nov["company"], nov["role"], nov["date"]), ("Novonesis", "Senior Principal Innovation PM", date(2026, 10, 12)))

    def test_missing_file(self):
        self.assertEqual(so.load_sends("/nonexistent/sends.json"), [])

    def test_real_register_parses(self):
        sends = so.load_sends()
        self.assertTrue(all(s["tag"] and s["company"] for s in sends))

    def test_row_tag(self):
        self.assertEqual(so.row_tag(row("/for-agents/start/acme-pm/", "x", meta={"tag": "acme-pm"})), "acme-pm")
        self.assertEqual(so.row_tag(row("/for-agents/start/novonesis.md", "x")), "novonesis")
        self.assertEqual(so.row_tag(row("/for-agents/start/novonesis", "x")), "novonesis")
        self.assertEqual(so.row_tag(row("/ask", "x", meta={"tag": "acme-pm"})), "acme-pm")
        self.assertIsNone(so.row_tag(row("/for-agents/start/", "x")))
        self.assertIsNone(so.row_tag(row("/for-agents/start.md", "x")))
        self.assertIsNone(so.row_tag(row("/ask", "x", meta={"tag": None})))


class Join(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sends.json")
            with open(p, "w") as fh:
                json.dump(SENDS_JSON, fh)
            self.sends = so.load_sends(p)
        self.joined, self.unknown = so.join(self.sends, STUB_ROWS, PIPELINE, TODAY)
        self.by = {j["tag"]: j for j in self.joined}

    def test_one_row_per_send(self):
        self.assertEqual(len(self.joined), 4)
        self.assertEqual(self.unknown, ["ghost-tag"])

    def test_counts(self):
        a = self.by["acme-pm"]
        self.assertEqual((a["fetches"], a["internal_fetches"], a["asks"], a["briefs"]), (2, 1, 2, 1))
        self.assertEqual(a["families"], {"OpenAI": 1, "Anthropic": 1})
        self.assertEqual((a["first_fetch"], a["last_fetch"]), (date(2026, 10, 3), date(2026, 10, 4)))
        self.assertEqual((a["days_since"], a["days_to_first_fetch"], a["days_to_reply"]), (19, 2, 5))
        self.assertEqual(a["outcome"], "interview")

    def test_path_only_rows_join(self):
        n = self.by["novonesis"]
        self.assertEqual(n["fetches"], 2)
        self.assertEqual(n["days_to_first_fetch"], 2)
        self.assertEqual((n["asks"], n["briefs"]), (0, 0))
        self.assertEqual(n["outcome"], "silent")
        self.assertIsNone(n["days_to_reply"])

    def test_internal_only_is_no_fetch(self):
        s = self.by["stale"]
        self.assertEqual((s["fetches"], s["internal_fetches"], s["first_fetch"]), (0, 1, None))
        self.assertEqual(s["outcome"], "rejected")   # matched by tag, not company

    def test_unfetched_reply(self):
        q = self.by["nofetch"]
        self.assertEqual((q["fetches"], q["outcome"], q["days_to_reply"]), (0, "reply", 4))

    def test_summary(self):
        s = so.summary(self.joined, True)
        self.assertEqual(s["sends"], 4)
        self.assertEqual(s["sends_with_fetch"], 2)
        self.assertEqual((s["fetched_replied"], s["unfetched"], s["unfetched_replied"]), (1, 2, 1))
        self.assertEqual(s["median_days_to_first_fetch"], 2)

    def test_median(self):
        self.assertIsNone(so.median([]))
        self.assertEqual(so.median([None, 3]), 3)
        self.assertEqual(so.median([1, 4, 2]), 2)
        self.assertEqual(so.median([1, 2, 3, 4]), 2.5)

    def test_outcome_order(self):
        self.assertEqual(so.outcome_of({"interview": "2026-10-15", "reply": "2026-10-06"}), ("interview", date(2026, 10, 6)))
        self.assertEqual(so.outcome_of({"interview": "2026-10-15"}), ("interview", date(2026, 10, 15)))
        self.assertEqual(so.outcome_of({"reply": "2026-10-06", "outcome": "Rejected"}), ("reply", date(2026, 10, 6)))
        self.assertEqual(so.outcome_of({"outcome": "rejected"}), ("rejected", None))
        self.assertEqual(so.outcome_of({"outcome": "No reply", "stage": "Dead"}), ("silent", None))
        self.assertEqual(so.outcome_of(None), ("silent", None))

    def test_pipeline_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "pipeline.csv")
            with open(p, "w") as fh:
                fh.write("Company,Role,Stage,Ball with,Outcome,Reply,Interview\n")
                fh.write("Acme,Head of Product,Active,Tom,,2026-10-06,\n")
            rows = so.load_pipeline(p)
        self.assertEqual(rows[0]["company"], "Acme")
        self.assertEqual(so.outcome_of(rows[0]), ("reply", date(2026, 10, 6)))
        self.assertIsNone(so.load_pipeline(None))


class NoPipeline(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sends.json")
            with open(p, "w") as fh:
                json.dump(SENDS_JSON, fh)
            self.sends = so.load_sends(p)
        self.report = so.build_report(STUB_ROWS, "staging", 60, TODAY, pipeline=None, sends=self.sends)

    def test_outcome_column(self):
        self.assertEqual(self.report.count("| pipeline not supplied |"), 4)
        self.assertIn("2. Fetched sends that replied vs unfetched sends that replied: pipeline not supplied.", self.report)
        self.assertIn("1. Tagged sends with any fetch: 2 of 4.", self.report)
        self.assertIn("3. Median days to first fetch: 2.", self.report)

    def test_with_pipeline(self):
        report = so.build_report(STUB_ROWS, "staging", 60, TODAY, pipeline=PIPELINE, sends=self.sends)
        self.assertIn("2. Fetched sends that replied: 1 of 2; unfetched sends that replied: 1 of 2.", report)
        self.assertIn("| interview |", report)
        self.assertNotIn("pipeline not supplied", report)
        self.assertIn("ghost-tag", report)

    def test_no_sends(self):
        report = so.build_report(STUB_ROWS, "staging", 60, TODAY, pipeline=None, sends=[])
        self.assertIn("1. Tagged sends with any fetch: 0 of 0.", report)
        self.assertIn("no fetches yet", report)


class Privacy(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sends.json")
            with open(p, "w") as fh:
                json.dump(SENDS_JSON, fh)
            self.sends = so.load_sends(p)
        self.reports = [so.build_report(STUB_ROWS, "staging", 60, TODAY, pipeline=pl, sends=self.sends) for pl in (None, PIPELINE)]

    def test_no_ip(self):
        for r in self.reports:
            self.assertNotIn("203.0.113.9", r)
            self.assertIsNone(re.search(r"\d{1,3}(?:\.\d{1,3}){3}", r))

    def test_no_visitor_text(self):
        for r in self.reports:
            self.assertNotIn(SECRET_QUESTION, r)
            self.assertNotIn("Novo Nordisk in 2023", r)
            self.assertNotIn("weird-agent", r)
            self.assertNotIn("claude.ai/chat", r)

    def test_no_long_user_agent(self):
        for r in self.reports:
            self.assertNotIn("AppleWebKit", r)
            self.assertNotIn("x" * 20, r)
            self.assertNotIn("y" * 20, r)
            for line in r.splitlines():
                if line.startswith("|"):
                    for cell in line.split("|"):
                        self.assertLess(len(cell.strip()), 60, cell)

    def test_only_outcome_words_from_pipeline(self):
        self.assertNotIn("Somebody Else", self.reports[1])   # pipeline companies reach the report only through sends.json
        self.assertNotIn("Ball with", self.reports[1])
        self.assertTrue(all(w in self.reports[1] for w in ("interview", "reply", "rejected", "silent")))

    def test_no_em_dash(self):
        for r in self.reports:
            self.assertNotIn(chr(0x2014), r)


if __name__ == "__main__":
    unittest.main()
