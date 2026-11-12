"""2026-11-12: observe public category keyboard behavior; CofactorMech #19.

Purpose: distinguish native browser/select interaction from filtering defects.
Inputs: --url public CofactorMech prefix, --executable browser, --evidence new
retained directory, optional --browser-label. Output: keyboard-diagnosis.json.
Observes focus, options, trusted events and row visibility on fresh page loads.
It does not change filters through DOM writes, source files or deployment state.
Programmatic select_option is a separately labelled control, not keyboard proof.
Requires Playwright 1.65.1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

SNAPSHOT = """() => {
 const select = document.querySelector('#category');
 const active = document.activeElement;
 const rows = [...document.querySelectorAll('[data-record]')].filter(row => !row.hidden);
 return {focused:{tag:active.tagName,id:active.id,value:active.value ?? null},
   select:{value:select.value,selectedIndex:select.selectedIndex,disabled:select.disabled,
     options:[...select.options].map(o=>({value:o.value,label:o.label,selected:o.selected}))},
   visible:rows.length,visibleCategories:rows.map(row=>row.dataset.categories),
   resultText:document.querySelector('#result-count').textContent,
   events:window.categoryKeyboardObservations};
}"""
OBSERVE = """() => {
 window.categoryKeyboardObservations = [];
 for (const kind of ['keydown','keyup','input','change','focusin','focusout']) {
   document.addEventListener(kind, event => {
     const select = document.querySelector('#category');
     window.categoryKeyboardObservations.push({type:event.type,key:event.key ?? null,
       targetId:event.target.id,isTrusted:event.isTrusted,defaultPrevented:event.defaultPrevented,
       value:select.value,selectedIndex:select.selectedIndex,
       activeId:document.activeElement.id,time:performance.now()});
   }, true);
 }
}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--browser-label', default='explicit-browser')
    args = parser.parse_args()
    assert args.url == 'https://culturebotai.github.io/CofactorMech/'
    args.evidence.mkdir(parents=True, exist_ok=False)
    result = {'at':datetime.now(timezone.utc).isoformat(), 'url':args.url,
              'browser_label':args.browser_label, 'cases':[], 'complete':False}
    sequences = [
        ('focused-arrows', ['ArrowDown','Enter']),
        ('focused-two-arrows', ['ArrowDown','ArrowDown','Enter']),
        ('focused-space', ['Space','ArrowDown','Enter']),
        ('focused-enter', ['Enter','ArrowDown','Enter']),
        ('focused-home', ['Home','ArrowDown','Enter']),
        ('focused-end', ['End','Enter']),
        ('focused-typeahead-c', ['c','Enter']),
        ('focused-alt-arrow', ['Alt+ArrowDown','ArrowDown','Enter']),
        ('tab-navigation-typeahead-c', ['c','Enter']),
        ('tab-navigation-end', ['End','Enter']),
        ('programmatic-control', []),
    ]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(args.executable))
            result['browser_version'] = browser.version
            for name, keys in sequences:
                context = browser.new_context(viewport={'width':1365,'height':900})
                page = context.new_page()
                case = {'name':name, 'steps':[], 'programmatic_control':name=='programmatic-control'}
                result['cases'].append(case)
                page.goto(args.url+'index.html', wait_until='networkidle')
                response = context.request.get(args.url+'site-manifest.json')
                assert response.status == 200
                manifest = response.json()
                result['revision'] = manifest['revision']
                result['manifest_sha256'] = hashlib.sha256(response.body()).hexdigest()
                page.evaluate(OBSERVE)
                case['initial'] = page.evaluate(SNAPSHOT)
                if name.startswith('tab-navigation'):
                    for _ in range(20):
                        if page.evaluate('document.activeElement.id') == 'category':
                            break
                        page.keyboard.press('Tab')
                        case['steps'].append({'key':'Tab','after':page.evaluate(SNAPSHOT)})
                    assert page.evaluate('document.activeElement.id') == 'category'
                else:
                    page.get_by_label('Category', exact=True).focus()
                case['focused'] = page.evaluate(SNAPSHOT)
                if name == 'programmatic-control':
                    page.get_by_label('Category', exact=True).select_option('COENZYME')
                for key in keys:
                    page.keyboard.press(key)
                    step = {'key':key,'immediate':page.evaluate(SNAPSHOT)}
                    page.wait_for_timeout(100)
                    step['after100ms'] = page.evaluate(SNAPSHOT)
                    page.wait_for_timeout(200)
                    step['after300ms'] = page.evaluate(SNAPSHOT)
                    case['steps'].append(step)
                final = page.evaluate(SNAPSHOT)
                case['final'] = final
                selected = final['select']['value']
                expected = manifest['categories'].get(selected)
                case['expected_count'] = expected
                case['correct_filtered_selection'] = bool(selected and expected
                    and 0 < expected < manifest['record_count'] and final['visible']==expected
                    and all(selected in categories.split('|')
                            for categories in final['visibleCategories']))
                context.close()
            browser.close()
        result['successful_keyboard_sequences'] = [case['name'] for case in result['cases']
            if not case['programmatic_control'] and case['correct_filtered_selection']]
        result['complete'] = True
    finally:
        (args.evidence/'keyboard-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'browser_version':result['browser_version'],
          'successful_keyboard_sequences':result['successful_keyboard_sequences'],
          'cases':[{k:c[k] for k in ['name','correct_filtered_selection','expected_count']}
                   for c in result['cases']]},indent=2))


if __name__ == '__main__':
    main()
