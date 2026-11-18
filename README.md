# allure-magic
Custom plugins for Allure report plus an optional failure-triage step.

![image](https://user-images.githubusercontent.com/13202196/218850713-1df77d91-5f30-4f7f-8361-e5aaff052a05.png)

## Layout
| Path | What |
|---|---|
| `global-info/` | Java Allure plugin (`GlobalInfoWidget`) + JS/CSS for the overview widget |
| `allure/allure-2.21.0/plugins/` | Allure distribution with the custom plugins (`global-info`, `restyle`, `custom-logo`) |
| `allure_magic/` | Python helpers: `global-info.json` writer, failure triage |
| `examples/` | Demo tests (some fail on purpose) to produce a sample report |
| `tests/` | Real tests for the Python code |

## Global Info widget
Write `allure-results/global-info.json` by hand or with `allure_magic.write_global_info`.
Decorations: `text` (default), `link`, `code` — all HTML-escaped; `html` renders raw HTML, use only with trusted content.
Links must be `http(s)://` or `mailto:`.

```python
from allure_magic import GlobalInfoItem, write_global_info
write_global_info([GlobalInfoItem("Build", "https://ci/1", "#1", "link")], "allure-results")
```

## Failure triage
Run after pytest, before generating the report:

```bash
pytest examples --alluredir=allure-results
python -m allure_magic.triage allure-results          # deterministic rules
python -m allure_magic.triage allure-results --llm    # + LLM (pip install anthropic, ANTHROPIC_API_KEY)
```
It groups similar failures (numbers/ids/paths ignored), labels each group
(product defect / test defect / environment), and writes `categories.json` plus
`Triage: ...` rows into `global-info.json`. Hand-written rows are preserved.
With `--llm`, logs are redacted (tokens, passwords, emails, JWTs) before sending, calls are capped by
`--max-groups`, the model is set via `ALLURE_MAGIC_MODEL`, and any API error falls back to the rules.

## Develop
```bash
pip install -e ".[dev]" && python -m pytest
gradle -p global-info build      # -> global-info/build/distributions
```
