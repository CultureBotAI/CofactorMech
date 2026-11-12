"""2026-11-12 site preparation: real browser checks; no deployment or data writes.

Purpose: verify the generated catalogue at a nested route on desktop/mobile and
without JavaScript. Inputs: --site, --evidence (durable empty output directory),
optional --executable browser binary. Outputs: screenshots and browser.json.
Tracking: CofactorMech #13 (mobile), #15 (receipts), #18 (console/icon).
Requires Playwright 1.65.1; the site itself has no browser-library dependency.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def contrast(foreground, background):
    def luminance(rgb):
        values = [int(x.strip()) / 255 for x in rgb.removeprefix("rgb(").removesuffix(")").split(",")]
        channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict=True))
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + 0.05) / (a + 0.05)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--executable", type=Path)
    args = parser.parse_args()
    site = args.site.resolve()
    args.evidence.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((site / "site-manifest.json").read_text())
    source = sorted((site / "sources").glob("*.yaml"))[0]
    record = json.loads(source.read_text())
    total = manifest["record_count"]
    handler = functools.partial(QuietHandler, directory=str(site.parent))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/{quote(site.name)}/index.html"
    errors = []
    failures = []
    result = {"at": datetime.now(timezone.utc).isoformat(), "project": manifest["project"],
              "manifest_sha256": hashlib.sha256((site / "site-manifest.json").read_bytes()).hexdigest(),
              "revision": manifest["revision"], "record_count": total, "checks": [], "passed": False}
    try:
        with sync_playwright() as p:
            options = {"headless": True}
            if args.executable:
                options["executable_path"] = str(args.executable)
            browser = p.chromium.launch(**options)
            result["browser_version"] = browser.version
            context = browser.new_context(viewport={"width": 1365, "height": 900})
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda message: errors.append(f"{message.text} ({message.location})") if message.type == "error" else None)
            page.on("requestfailed", lambda r: failures.append(r.url))
            page.goto(url, wait_until="networkidle")
            assert page.locator("[data-record]:visible").count() == total
            result["contrast_probes"] = []
            for selector in ("body", ".hero h1", "#search-help", ".brand", "table a", "button", "small", ".badge"):
                pair = page.locator(selector).first.evaluate("""el => {
                    let node = el, background;
                    do { background = getComputedStyle(node).backgroundColor; node = node.parentElement; }
                    while (node && background === 'rgba(0, 0, 0, 0)');
                    return {foreground: getComputedStyle(el).color, background};
                }""")
                ratio = contrast(pair["foreground"], pair["background"])
                result["contrast_probes"].append(dict(selector=selector, ratio=ratio, **pair))
                assert ratio >= 4.5, (selector, pair, ratio)
            page.screenshot(path=str(args.evidence / "catalogue-desktop.png"), full_page=True)
            page.keyboard.press("Tab")
            assert page.locator(".skip").evaluate("el => el === document.activeElement")
            page.keyboard.press("Enter")
            assert page.locator("#main").evaluate("el => el === document.activeElement")
            search = page.get_by_label("Search names or identifiers")
            search.focus()
            assert search.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
            search.fill(record["id"])
            assert page.locator("[data-record]:visible").count() == 1
            search.fill(record["name"])
            assert page.locator("[data-record]:visible").count() >= 1
            page.get_by_role("button", name="Reset filters").click()
            category = page.get_by_label("Category", exact=True)
            category.focus()
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            assert 0 < page.locator("[data-record]:visible").count() <= total
            page.get_by_role("button", name="Reset filters").click()
            assert page.locator("[data-record]:visible").count() == total
            search.fill("<img src=x onerror=alert(1)>")
            assert page.locator("[data-record]:visible").count() == 0
            assert page.locator("#no-results").is_visible()
            assert page.locator("img").count() == 0
            page.goto(url + "?q=" + quote("<script>alert(1)</script>"), wait_until="networkidle")
            assert page.locator("#no-results").is_visible()
            page.get_by_role("button", name="Reset filters").click()
            page.set_viewport_size({"width": 390, "height": 844})
            viewport = page.evaluate("""() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
                headings: [...document.querySelectorAll('h1,h2,h3,p')].filter(e => e.getBoundingClientRect().right > innerWidth).map(e => ({tag:e.tagName,text:e.textContent,width:e.getBoundingClientRect().width}))})""")
            result.setdefault("viewport_probes", []).append(viewport)
            if viewport["scroll"] > viewport["width"]:
                page.screenshot(path=str(args.evidence / "failure.png"), full_page=True)
            assert viewport["scroll"] <= viewport["width"], viewport
            table = page.locator(".table-scroll").first
            table.focus()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(250)
            assert table.evaluate("el => el.scrollLeft > 0")
            page.screenshot(path=str(args.evidence / "catalogue-mobile.png"), full_page=True)
            page.locator(f'a[href="records/{source.stem}/index.html"]').click()
            page.wait_for_load_state("networkidle")
            assert record["id"] in page.locator("main").inner_text()
            assert page.get_by_role("heading", name="Research gaps", exact=True).is_visible()
            viewport = page.evaluate("""() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
                headings: [...document.querySelectorAll('h1,h2,h3,p')].filter(e => e.getBoundingClientRect().right > innerWidth).map(e => ({tag:e.tagName,text:e.textContent,width:e.getBoundingClientRect().width}))})""")
            result.setdefault("viewport_probes", []).append(viewport)
            if viewport["scroll"] > viewport["width"]:
                page.screenshot(path=str(args.evidence / "failure.png"), full_page=True)
            assert viewport["scroll"] <= viewport["width"], viewport
            yaml_link = page.get_by_role("link", name="Download source YAML")
            response = context.request.get(yaml_link.get_attribute("href") if yaml_link.get_attribute("href").startswith("http")
                                           else page.evaluate("document.querySelector('a[download], a[href*=\"/sources/\"]').href"))
            assert response.ok and response.body() == source.read_bytes()
            evidence = page.get_by_role("link", name="Source reference", exact=True).first
            expected = record["evidence"][0]["reference"]
            assert evidence.get_attribute("href") == expected
            result["representative_evidence_href"] = expected
            # External sources are not fetched by the site. Probe this one without hiding failures.
            try:
                ext = context.request.get(expected, timeout=20000)
                result["external_reference_http_status"] = ext.status
            except Exception as exc:
                result["external_reference_probe"] = type(exc).__name__
            page.screenshot(path=str(args.evidence / "record-mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1365, "height": 900})
            page.screenshot(path=str(args.evidence / "record-desktop.png"), full_page=True)
            page.get_by_role("link", name="← Cofactor catalogue").click()
            assert page.locator("[data-record]:visible").count() == total
            context.close()
            nojs = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
            page = nojs.new_page()
            page.goto(url, wait_until="networkidle")
            assert page.locator("[data-record]:visible").count() == total
            assert not page.locator("#controls").is_visible()
            page.locator(f'a[href="records/{source.stem}/index.html"]').click()
            assert record["id"] in page.locator("main").inner_text()
            assert page.get_by_role("link", name="Source reference", exact=True).count() >= 1
            page.screenshot(path=str(args.evidence / "record-nojs-mobile.png"), full_page=True)
            nojs.close()
            browser.close()
        assert not errors and not failures, (errors, failures)
        result["checks"] = ["complete desktop/mobile catalogue", "identifier/name search",
                            "category/reset", "literal query and zero results", "keyboard skip/focus/scroll",
                            "nested catalogue/detail/YAML/evidence links", "no-JS catalogue/detail",
                            "no viewport overflow", "computed text contrast >= 4.5", "no page errors or failed site requests"]
        result["screenshots_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in args.evidence.glob("*.png")}
        result["passed"] = True
    finally:
        server.shutdown()
        server.server_close()
        result.update(page_errors=errors, failed_requests=failures)
        (args.evidence / "browser.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
