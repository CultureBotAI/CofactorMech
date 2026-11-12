"""2026-11-12 public catalogue verification; reads HTTP, writes local evidence only.

Purpose: compare the published CofactorMech site to its downloaded deployment
artifacts and exercise the actual public URL in desktop/mobile/no-JS browsers.
Inputs: --url (exact public prefix), --site (complete catalogue-site artifact),
--pages-site (extracted github-pages tar), --revision (full expected merge SHA),
--evidence (new durable directory), and optional --executable.
Outputs: browser.json with archive inventories, category-guard fixture and
hash-bound screenshots. Tracking: CofactorMech #16 publication and #19 category
guard correction; follows the reviewed local browser helper. The pinned Pages
packager excludes dotfiles; those remain bound to the complete review artifact.
Requires Playwright 1.65.1. Does not deploy, alter records or call research tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from playwright.sync_api import sync_playwright


def contrast(foreground, background):
    def luminance(rgb):
        values = [int(x.strip()) / 255 for x in rgb.removeprefix("rgb(").removesuffix(")").split(",")]
        channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(channels, (0.2126, 0.7152, 0.0722), strict=True))
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + 0.05) / (a + 0.05)


def verify_artifact_pair(site, pages_site, manifest, result):
    """Require precisely the pinned Pages packager's two known exclusions."""
    review_inventory = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    pages_inventory = {p.relative_to(pages_site).as_posix()
                       for p in pages_site.rglob("*") if p.is_file()}
    excluded = {".nojekyll", ".site-generated"}
    assert not any(p.is_symlink() for root in (site, pages_site) for p in root.rglob("*"))
    assert review_inventory == set(manifest["files_sha256"]) | {"site-manifest.json"}
    assert excluded <= review_inventory
    assert pages_inventory == review_inventory - excluded, "Pages archive inventory differs"
    hashes = {}
    for name in sorted(pages_inventory):
        content = (pages_site / name).read_bytes()
        assert content == (site / name).read_bytes(), (name, "Pages/review archive bytes differ")
        hashes[name] = hashlib.sha256(content).hexdigest()
    result["archive_inventory_proof"] = {
        "review_files": sorted(review_inventory), "pages_files": sorted(pages_inventory),
        "excluded_review_markers": sorted(excluded), "pages_files_sha256": hashes,
        "pages_packager_revision": "7b1f4a764d45c48632c6b24a0339c27f5614fb0b",
        "packager_exclusion": '--exclude=".[^/]*"', "all_pages_bytes_equal_review": True,
    }


def verify_selected_category(selected, visible_categories, manifest):
    """Reject a nonfunctional selector, wrong count, or wrong visible membership."""
    assert selected and selected in manifest["categories"], "category selection is empty/unknown"
    expected = manifest["categories"][selected]
    assert 0 < expected < manifest["record_count"], "category does not narrow the corpus"
    assert len(visible_categories) == expected, "selected-category visible count differs"
    assert all(selected in categories.split("|") for categories in visible_categories), \
        "visible record is outside selected category"
    return {"selected": selected, "expected": expected, "visible": len(visible_categories),
            "all_visible_records_belong": True}


def no_op_category_fixture(manifest, all_categories):
    """Deliberately leave every row visible: the previous weak check passed this."""
    selected = next(name for name, count in manifest["categories"].items()
                    if 0 < count < manifest["record_count"])
    assert len(all_categories) == manifest["record_count"]
    weak_check = 0 < len(all_categories) <= manifest["record_count"]
    try:
        verify_selected_category(selected, all_categories, manifest)
    except AssertionError:
        return {"fixture": "selected category with no-op filtering; all rows remain visible",
                "selected": selected, "visible": len(all_categories),
                "expected": manifest["categories"][selected],
                "previous_weak_predicate_accepts": weak_check, "corrected_guard_rejects": True}
    raise AssertionError("no-op category fixture escaped corrected guard")


def verify_public_files(request, prefix, site, manifest, result):
    """Bind all review artifact files and every published byte to the manifest."""
    expected_files = manifest["files_sha256"]
    inventory = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    assert inventory == set(expected_files) | {"site-manifest.json"}, "artifact inventory differs"
    assert not any(p.is_symlink() for p in site.rglob("*")), "artifact contains a symlink"
    rows = []
    result["public_files"] = rows
    for name in ["site-manifest.json", *sorted(expected_files)]:
        relative = PurePosixPath(name)
        assert not relative.is_absolute() and ".." not in relative.parts
        assert relative.as_posix() == name and "\\" not in name
        local = (site / name).read_bytes()
        digest = hashlib.sha256(local).hexdigest()
        if name != "site-manifest.json":
            assert digest == expected_files[name], (name, "artifact digest differs")
        target = prefix + quote(name, safe="/")
        response = request.get(target, timeout=30000)
        row = {"path": name, "status": response.status, "artifact_sha256": digest}
        rows.append(row)
        assert response.url == target, (name, "unexpected redirect")
        if name in {".nojekyll", ".site-generated"} and response.status in {403, 404}:
            row["verification"] = "review_artifact_only"
            row["reason"] = "Pinned upload-pages-artifact excludes this generated dotfile"
            continue
        assert response.status == 200, (name, response.status)
        served = response.body()
        row.update(served_sha256=hashlib.sha256(served).hexdigest(), bytes=len(served))
        assert served == local, (name, "published bytes differ from deployment artifact")
        row["verification"] = "public_bytes_identical"
    root_response = request.get(prefix, timeout=30000)
    assert root_response.status == 200 and root_response.url == prefix
    assert root_response.body() == (site / "index.html").read_bytes()
    result["public_root"] = {"url": prefix, "status": root_response.status,
                             "sha256": hashlib.sha256(root_response.body()).hexdigest()}


def observe_context(context, errors, failures, http_errors, prefix):
    """Observe every page, including no-JS, without redirecting browser traffic."""
    def observe(page):
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text)
                if message.type == "error" else None)
        page.on("requestfailed", lambda request: failures.append(request.url))
        page.on("response", lambda response: http_errors.append(
            {"url": response.url, "status": response.status}) if response.status >= 400 else None)
        page.on("framenavigated", lambda frame: errors.append("unexpected navigation: " + frame.url)
                if frame == page.main_frame and frame.url != "about:blank"
                and not frame.url.startswith(prefix) else None)
    context.on("page", observe)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--pages-site", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--executable", type=Path)
    args = parser.parse_args()
    assert args.url == "https://culturebotai.github.io/CofactorMech/", "unexpected public prefix"
    assert re.fullmatch(r"[0-9a-f]{40}", args.revision), "expected full merge SHA"
    assert not args.site.is_symlink() and not args.pages_site.is_symlink(), "artifact root symlink"
    site = args.site.resolve()
    pages_site = args.pages_site.resolve()
    args.evidence.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((site / "site-manifest.json").read_text())
    source = sorted((site / "sources").glob("*.yaml"))[0]
    record = json.loads(source.read_text())
    total = manifest["record_count"]
    url = args.url + "index.html"
    errors = []
    failures = []
    http_errors = []
    result = {"at": datetime.now(timezone.utc).isoformat(), "project": manifest["project"],
              "manifest_sha256": hashlib.sha256((site / "site-manifest.json").read_bytes()).hexdigest(),
              "revision": manifest["revision"], "record_count": total, "public_url": args.url, "checks": [], "passed": False}
    try:
        assert manifest["project"] == "CofactorMech" and manifest["revision"] == args.revision
        assert total > 0
        verify_artifact_pair(site, pages_site, manifest, result)
        with sync_playwright() as p:
            options = {"headless": True}
            if args.executable:
                options["executable_path"] = str(args.executable)
            browser = p.chromium.launch(**options)
            result["browser_version"] = browser.version
            context = browser.new_context(viewport={"width": 1365, "height": 900})
            verify_public_files(context.request, args.url, site, manifest, result)
            observe_context(context, errors, failures, http_errors, args.url)
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            assert page.locator("[data-record]:visible").count() == total
            all_categories = page.locator("[data-record]:visible").evaluate_all(
                "rows => rows.map(row => row.dataset.categories)")
            result["category_guard_fixture"] = no_op_category_fixture(manifest, all_categories)
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
            # The retained keyboard diagnostic verifies trusted input/change
            # events for native typeahead; arrows did not move this browser's select.
            result["category_keyboard_sequence"] = ["c", "Enter"]
            for key in result["category_keyboard_sequence"]:
                page.keyboard.press(key)
            result["category_selection"] = verify_selected_category(
                category.input_value(), page.locator("[data-record]:visible").evaluate_all(
                    "rows => rows.map(row => row.dataset.categories)"), manifest)
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
            observe_context(nojs, errors, failures, http_errors, args.url)
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
        assert not errors and not failures and not http_errors, (errors, failures, http_errors)
        result["checks"] = ["complete desktop/mobile catalogue", "identifier/name search",
                            "category/reset", "literal query and zero results", "keyboard skip/focus/scroll",
                            "nested catalogue/detail/YAML/evidence links", "no-JS catalogue/detail",
                            "no viewport overflow", "computed text contrast >= 4.5",
                            "no JS/no-JS page, console, HTTP or request errors",
                            "published manifest and public files match deployment artifact",
                            "exact review/Pages archive inventory and byte comparison",
                            "explicit generated-dotfile review-artifact-only exceptions",
                            "category count and membership; no-op mutation rejected"]
        result["screenshots_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in args.evidence.glob("*.png")}
        result["passed"] = True
    finally:
        result.update(page_errors=errors, failed_requests=failures, http_errors=http_errors)
        (args.evidence / "browser.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
