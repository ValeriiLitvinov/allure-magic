import json

from allure_magic import GlobalInfoItem, write_global_info
from allure_magic.classify import LLMClassifier, classify_by_rules, parse_llm_json
from allure_magic.redact import redact
from allure_magic.results import fingerprint, group_failures, load_failures
from allure_magic.triage import TRIAGE_PREFIX, main


def make(tmp, uid, status, message, trace="", name=None):
    (tmp / f"{uid}-result.json").write_text(
        json.dumps({"uuid": uid, "name": name or uid, "status": status,
                    "statusDetails": {"message": message, "trace": trace}})
    )


def seed(tmp):
    make(tmp, "a1", "failed", "AssertionError: assert 1 == 2", "E   AssertionError")
    make(tmp, "a2", "failed", "AssertionError: assert 7 == 9", "E   AssertionError")
    make(tmp, "b1", "broken", "ZeroDivisionError: division by zero", "E   ZeroDivisionError")
    make(tmp, "c1", "broken", "requests.exceptions.ConnectionError: Max retries exceeded host:8080")
    make(tmp, "ok", "passed", "")
    (tmp / "garbage-result.json").write_text("{not json")


def test_load_skips_passed_and_garbage(tmp_path):
    seed(tmp_path)
    assert {f.uuid for f in load_failures(tmp_path)} == {"a1", "a2", "b1", "c1"}


def test_grouping_ignores_numbers(tmp_path):
    seed(tmp_path)
    groups = group_failures(load_failures(tmp_path))
    assert [g.size for g in groups] == [2, 1, 1]
    f = load_failures(tmp_path)
    assert fingerprint(f[0]) == fingerprint(f[1])


def test_rules(tmp_path):
    seed(tmp_path)
    cats = {g.representative.uuid: classify_by_rules(g).category for g in group_failures(load_failures(tmp_path))}
    assert cats == {"a1": "product_defect", "b1": "test_defect", "c1": "environment"}


def test_redact_masks_secrets():
    text = "token=abc123secret Authorization: Bearer abcdefghijkl user@mail.com https://u:pw@host/x"
    out = redact(text)
    for leaked in ("abc123secret", "abcdefghijkl", "user@mail.com", "u:pw"):
        assert leaked not in out
    assert len(redact("x" * 10000)) < 4200


def test_parse_llm_json():
    assert parse_llm_json('noise {"category":"environment","confidence":2,"reason":"r"}').confidence == 1.0
    assert parse_llm_json('{"category":"bogus"}') is None
    assert parse_llm_json("no json") is None


class FakeClient:
    def __init__(self, text=None, boom=False):
        self.text, self.boom, self.prompts = text, boom, []
        self.messages = self

    def create(self, **kw):
        self.prompts.append(kw["messages"][0]["content"])
        if self.boom:
            raise RuntimeError("api down")
        block = type("B", (), {"text": self.text})()
        return type("R", (), {"content": [block]})()


def test_llm_used_and_redacted(tmp_path):
    make(tmp_path, "x", "failed", "AssertionError: password=hunter2")
    group = group_failures(load_failures(tmp_path))[0]
    client = FakeClient('{"category":"environment","confidence":0.9,"reason":"flaky infra"}')
    v = LLMClassifier(client=client, model="m")(group)
    assert (v.category, v.source) == ("environment", "llm")
    assert "hunter2" not in client.prompts[0]


def test_llm_failure_falls_back_to_rules(tmp_path):
    make(tmp_path, "x", "failed", "AssertionError: boom")
    group = group_failures(load_failures(tmp_path))[0]
    assert LLMClassifier(client=FakeClient(boom=True), model="m")(group).source == "rules"


def test_cli_writes_files_and_keeps_manual_rows(tmp_path):
    seed(tmp_path)
    write_global_info([GlobalInfoItem("Manual", "keep me"), GlobalInfoItem(TRIAGE_PREFIX + "old", "stale")], tmp_path)
    assert main([str(tmp_path)]) == 0
    assert main([str(tmp_path)]) == 0  # idempotent
    names = [i["name"] for i in json.loads((tmp_path / "global-info.json").read_text())]
    assert names[0] == "Manual" and "Triage: old" not in names
    assert sum(n.startswith(TRIAGE_PREFIX) for n in names) == 4  # summary + 3 groups
    cats = json.loads((tmp_path / "categories.json").read_text())
    assert len(cats) == 3 and all(c["matchedStatuses"] for c in cats)


def test_cli_missing_dir(tmp_path):
    assert main([str(tmp_path / "nope")]) == 2
