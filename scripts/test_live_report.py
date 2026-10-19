#!/usr/bin/env python3
"""Tests for scripts/live_report.py: stubbed rows, no network, no database.

    python3 scripts/test_live_report.py
"""

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_report as lr  # noqa: E402

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
LONG_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 " + "x" * 80
SECRET_QUESTION = "what did Tom do at Novo Nordisk in 2023"


def row(path, ua, hours=0, status=200, meta=None, referer=None):
    return dict(created_at=T0 + timedelta(hours=hours), path=path, user_agent=ua, referer=referer, status=status, meta=meta)


STUB_ROWS = [
    row("/for-agents/", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.1; +https://openai.com/gptbot)"),
    row("/for-agents/", "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", hours=1),
    row("/for-agents/start.md", "Mozilla/5.0 (compatible; PerplexityBot/1.0)", hours=2),
    row("/llms.txt", "Mozilla/5.0 (compatible; Googlebot/2.1)", hours=26, status=404),
    row("/for-agents/novo-nordisk/", "tbn-check-staging/1.0 (+https://takenbyninjas.com/for-agents/)", hours=27),
    row("/for-agents/", LONG_UA, hours=28, referer="https://claude.ai/chat"),
    row("/for-agents/start/acme-pm.md", "curl/8.7.1", hours=29, meta={"tag": "acme-pm"}),
    # a visitor-controlled user agent carrying an IP and a question, which must never reach the report
    row("/for-agents/", "weird-agent/1.0 ip=203.0.113.9 q=" + SECRET_QUESTION + " " + "y" * 100, hours=30),
    row("/ask", "ChatGPT-User/1.0", hours=3, meta={"tag": "acme-pm", "asker": "recruiter-agent", "query_length": 30, "section": "FIT.TEAM", "matches": 1, "withheld": 0}),
    row("/ask", "ChatGPT-User/1.0", hours=4, meta={"tag": None, "asker": None, "query_length": 20, "section": None, "matches": 0, "withheld": 0}),
    row("/ask", "Claude-User/1.0", hours=5, meta={"tag": None, "asker": SECRET_QUESTION, "query_length": 44, "section": None, "matches": 0, "withheld": 0, "flags": ["injection_pattern"]}),
    row("/ask", "Claude-User/1.0", hours=31, meta={"tag": "acme-pm", "asker": "human", "query_length": 25, "section": "FIT.TEAM", "matches": 2, "withheld": 1}),
    row("/ask/brief", "Claude-User/1.0", hours=32, meta={"asker": "hiring-manager", "tag": "acme-pm", "requirements": 5, "met": 2, "partial": 2, "not_met": 1, "splitter": "llm",
                                                        "proof_point_rows": 1, "evidence_queries": 6, "adjacent": 1, "facts": ["location"], "facts_not_stated": ["start_date"],
                                                        "seniority": "head", "function": "product", "sector": "pharma"}),
    row("/ask/brief", "python-requests/2.31", hours=33, meta={"asker": None, "tag": None, "requirements": 3, "met": 0, "partial": 1, "not_met": 2, "splitter": "heuristic",
                                                              "proof_point_rows": 0, "evidence_queries": 0, "adjacent": 0, "facts": [], "facts_not_stated": [],
                                                              "seniority": "unknown", "function": "product", "sector": "unknown"}),
]

UMAMI_REFERRERS = [{"x": "chatgpt.com", "y": 3}, {"x": "www.google.com", "y": 40}, {"x": "claude.ai", "y": 2},
                   {"x": "bing.com", "y": 5}, {"x": "bing.com/chat", "y": 1}, {"x": "linkedin.com", "y": 9}]


class FamilyTable(unittest.TestCase):
    def test_families(self):
        cases = {
            "Mozilla/5.0 (compatible; GPTBot/1.1)": "OpenAI",
            "ChatGPT-User/1.0": "OpenAI",
            "OAI-SearchBot/1.0": "OpenAI",
            "ClaudeBot/1.0": "Anthropic",
            "Claude-User/1.0": "Anthropic",
            "anthropic-ai": "Anthropic",
            "PerplexityBot/1.0": "Perplexity",
            "Google-Extended": "Google",
            "Googlebot/2.1": "Google",
            "bingbot/2.0": "Microsoft",
            "Microsoft Copilot": "Microsoft",
            "tbn-agent-health/1.0": "internal (tbn-*)",
            "curl/8.7.1": "curl",
            "python-requests/2.31": "python",
            "SomethingBot/0.1": "other bot",
            "Mozilla/5.0 (Macintosh)": "browser",
            "weird-agent/1.0": "other",
            "": "(empty)",
            None: "(empty)",
        }
        for ua, expected in cases.items():
            self.assertEqual(lr.family(ua), expected, ua)

    def test_short_ua(self):
        self.assertLessEqual(len(lr.short_ua(LONG_UA)), lr.UA_MAX)
        self.assertEqual(lr.short_ua(LONG_UA), "Mozilla/5.0")
        self.assertEqual(lr.short_ua("weird-agent/1.0 ip=203.0.113.9 q=secret"), "weird-agent/1.0")
        self.assertEqual(lr.short_ua("bot-203.0.113.9/1.0"), "bot-[ip]/1.0")
        self.assertEqual(lr.short_ua(None), "")


class Aggregation(unittest.TestCase):
    def setUp(self):
        self.agg = lr.aggregate(STUB_ROWS)

    def test_fetches(self):
        f = self.agg["fetches"]
        self.assertEqual(f["total"], 8)
        self.assertEqual(f["by_path"]["/for-agents/"], 4)
        self.assertEqual(f["by_family"]["OpenAI"], 1)
        self.assertEqual(f["by_family"]["browser"], 1)
        self.assertEqual(f["by_family"]["other"], 1)
        self.assertEqual(f["non_200"]["Google"], 1)
        self.assertEqual(f["by_day"]["2026-10-12"], 3)
        self.assertEqual(f["by_day"]["2026-10-13"], 5)
        self.assertEqual(f["referers"]["https://claude.ai/chat"], 1)
        self.assertEqual(f["tagged_start"]["acme-pm"], 1)
        self.assertEqual(f["crawlers_on_agent_index"], ["Anthropic", "OpenAI"])

    def test_usage(self):
        u = self.agg["usage"]
        self.assertEqual(u["ask_calls"], 4)
        self.assertEqual(u["brief_calls"], 2)
        self.assertEqual(u["by_tag"]["acme-pm"], 3)
        self.assertEqual(u["by_tag"]["(none)"], 3)
        self.assertEqual(dict(u["by_asker"]), {"recruiter-agent": 1, "(none)": 2, "other": 1, "human": 1, "hiring-manager": 1})
        self.assertEqual(u["external_brief_calls"], 1)
        self.assertEqual(u["external_tagged_calls"], 3)
        self.assertEqual(u["by_asker"]["other"], 1)
        self.assertEqual(u["sections"]["FIT.TEAM"], 2)
        self.assertEqual(u["ask_null"], 2)
        self.assertAlmostEqual(u["ask_null_rate"], 0.5)
        self.assertEqual(u["ask_withheld"], 1)
        self.assertEqual(u["flags"]["injection_pattern"], 1)
        self.assertEqual(u["by_day"][("2026-10-13", "/ask/brief")], 2)
        b = u["brief"]
        self.assertEqual((b["requirements"], b["met"], b["partial"], b["not_met"]), (8, 2, 3, 3))
        self.assertEqual(b["splitter"]["llm"], 1)
        self.assertEqual(b["facts_not_stated"]["start_date"], 1)
        self.assertEqual(u["shapes"]["function"]["product"], 2)
        self.assertEqual(u["not_met_by_shape"]["sector"]["unknown"], 2)
        self.assertEqual(u["not_met_by_shape"]["sector"]["pharma"], 1)

    def test_empty(self):
        agg = lr.aggregate([])
        self.assertEqual(agg["fetches"]["total"], 0)
        self.assertEqual(agg["usage"]["ask_null_rate"], 0.0)
        s4 = lr.s4_converts(agg, None)
        self.assertEqual(s4["converts"], 0)
        self.assertIsNone(s4["ai_referrer_visits"])
        text = lr.render(agg, None, "no key", s4, "production", 7, "2026-10-14", table_note="table agent_fetches does not exist")
        self.assertIn("Agent fetches: 0", text)
        self.assertIn("not available: no key", text)
        self.assertIn("table agent_fetches does not exist", text)


class Umami(unittest.TestCase):
    def test_classify(self):
        ai = lr.classify_referrers(UMAMI_REFERRERS)
        self.assertEqual(dict(ai), {"chatgpt.com": 3, "claude.ai": 2, "bing.com/chat": 1})

    def test_subprocess_failure_is_a_reason(self):
        def runner(cmd):
            return "", "No Umami API key. Put it in /home/x/.config/umami/api-key", 1
        if lr.find_stats_mjs() is None:
            self.skipTest("stats.mjs not on this machine")
        result, reason = lr.umami_ai_referrers(7, runner=runner)
        self.assertIsNone(result)
        self.assertIn("No Umami API key", reason)

    def test_subprocess_json(self):
        def runner(cmd):
            return json.dumps({"referrers": UMAMI_REFERRERS}), "", 0
        if lr.find_stats_mjs() is None:
            self.skipTest("stats.mjs not on this machine")
        result, reason = lr.umami_ai_referrers(7, runner=runner)
        self.assertIsNone(reason)
        self.assertEqual(sum(result.values()), 6)


class S4(unittest.TestCase):
    def test_converts(self):
        agg = lr.aggregate(STUB_ROWS)
        s4 = lr.s4_converts(agg, lr.classify_referrers(UMAMI_REFERRERS))
        # 6 AI visits + 3 tagged calls (all from ChatGPT/Claude agents) + 1 external brief (the python one is internal)
        self.assertEqual(s4["converts"], 10)
        self.assertEqual(s4["tagged_calls"], 3)
        self.assertEqual(s4["brief_calls"], 1)
        self.assertEqual(s4["all_brief_calls"], 2)
        self.assertEqual(s4["crawlers_on_agent_index"], ["Anthropic", "OpenAI"])


class Privacy(unittest.TestCase):
    def setUp(self):
        agg = lr.aggregate(STUB_ROWS)
        s4 = lr.s4_converts(agg, lr.classify_referrers(UMAMI_REFERRERS))
        self.text = lr.render(agg, lr.classify_referrers(UMAMI_REFERRERS), None, s4, "staging", 7, "2026-10-14")

    def test_no_ip(self):
        self.assertIsNone(re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", self.text))

    def test_no_visitor_text(self):
        self.assertNotIn(SECRET_QUESTION, self.text)
        self.assertNotIn("Novo Nordisk", self.text)

    def test_no_long_user_agent(self):
        for m in re.finditer(r"`([^`]+)`", self.text):
            self.assertLessEqual(len(m.group(1)), lr.UA_MAX, m.group(1))
        self.assertNotIn("x" * 61, self.text)
        self.assertNotIn("y" * 61, self.text)
        self.assertNotIn("Chrome/130.0", self.text)

    def test_no_query_strings(self):
        self.assertIsNone(re.search(r"https?://\S*\?", self.text))

    def test_no_em_dash(self):
        self.assertNotIn("—", self.text)

    def test_asker_bucketed(self):
        self.assertIn("| other | 1 |", self.text)


class FakeCursor:
    def __init__(self, exists):
        self.exists = exists
        self.last = None

    def execute(self, sql, params=None):
        self.last = sql

    def fetchone(self):
        return ("agent_fetches" if self.exists else None,)

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConn:
    def __init__(self, exists):
        self.exists = exists

    def cursor(self):
        return FakeCursor(self.exists)

    def rollback(self):
        pass


class MissingTable(unittest.TestCase):
    def test_missing_table_gives_zeros(self):
        rows, note = lr.fetch_rows(FakeConn(exists=False), 7)
        self.assertEqual(rows, [])
        self.assertIn("does not exist", note)
        text = lr.build_report(rows, "production", 7, "2026-10-14", table_note=note, ai_result=(None, "skipped"), runs_dir=tempfile.mkdtemp())
        self.assertIn("Agent fetches: 0", text)
        self.assertIn("| 0 | n/a | 0 | 0 of 0 | 0 of 5 |", text)

    def test_present_but_empty(self):
        rows, note = lr.fetch_rows(FakeConn(exists=True), 7)
        self.assertEqual((rows, note), ([], None))


class Delta(unittest.TestCase):
    def test_previous_and_delta(self):
        with tempfile.TemporaryDirectory() as d:
            agg = lr.aggregate(STUB_ROWS[:6])
            s4 = lr.s4_converts(agg, None)
            first = lr.render(agg, None, "skipped", s4, "staging", 7, "2026-10-13")
            with open(os.path.join(d, "2026-10-13-live.md"), "w") as fh:
                fh.write(first)
            # a file without a numbers block is ignored, a newer-dated one too
            with open(os.path.join(d, "2026-10-11-live.md"), "w") as fh:
                fh.write("# old, no numbers\n")
            with open(os.path.join(d, "2026-10-20-live.md"), "w") as fh:
                fh.write("<!-- live-numbers {\"fetches\": 999} -->\n")
            prev = lr.previous_report(d, "2026-10-14")
            self.assertEqual(prev["name"], "2026-10-13-live.md")
            self.assertEqual(prev["numbers"]["fetches"], 6)
            self.assertEqual(prev["numbers"]["ask_calls"], 0)

            text = lr.build_report(STUB_ROWS, "staging", 7, "2026-10-14", ai_result=(lr.classify_referrers(UMAMI_REFERRERS), None), runs_dir=d)
            self.assertIn("## 6. Delta against 2026-10-13-live.md", text)
            self.assertIn("| fetches | 6 | 8 | +2 |", text)
            self.assertIn("| ask_calls | 0 | 4 | +4 |", text)
            self.assertIn("| ai_referrer_visits | 0 | 6 | +6 |", text)

    def test_no_previous(self):
        with tempfile.TemporaryDirectory() as d:
            text = lr.build_report(STUB_ROWS, "staging", 7, "2026-10-14", runs_dir=d)
            self.assertNotIn("Delta against", text)
            self.assertIn("<!-- live-numbers ", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
