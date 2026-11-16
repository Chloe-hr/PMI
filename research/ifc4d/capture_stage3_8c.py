"""Optional browser acceptance and screenshot capture. Requires playwright and installed Edge.
Start app.py with Streamlit first. Does not regenerate Stage 3.8B artifacts.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from research.ifc4d import viewer_data as data

ROOT=Path(__file__).resolve().parents[2]


def capture(url,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    bundle=data.load_bundle(ROOT/"data/processed/ifc4d/stage3_8b_v1")
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="msedge",headless=True)
        page=browser.new_page(viewport={"width":2000,"height":1800},device_scale_factor=1)
        page.goto(url+"/IFC4D_Synthetic")
        def ready(project,rep="as_provided"):
            page.wait_for_function("""([project,rep])=>{
                const charts=document.querySelectorAll('.js-plotly-plot');
                return charts.length===2 && charts[0].data?.[0]?.customdata?.[0]?.[11]===project &&
                       charts[0].data.some(d=>d.customdata?.[0]?.[14]===rep);
            }""",arg=[project,rep],timeout=30000)
            page.get_by_role("heading",name="Dependency validation",exact=False).wait_for()
            assert page.locator('[data-testid="stException"]').count()==0
        def choose(label,value):
            combo=page.get_by_role("combobox",name=label,exact=True)
            combo.evaluate("el=>el.scrollIntoView({block:'center'})")
            combo.focus()
            combo.press("ArrowDown")
            combo.fill(value)
            page.get_by_role("option",name=value,exact=True).click()
        ready("SYN-BRG-001")
        # Real SVG pointer click, not a simulated Streamlit callback.
        bar=page.locator('.js-plotly-plot').first.locator('.barlayer .trace').first.locator('.point path').nth(12)
        bar.evaluate("el=>el.scrollIntoView({block:'center'})")
        box=bar.bounding_box()
        # Plotly routes pointer events through its transparent interaction overlay.
        page.mouse.click(box["x"]+box["width"]/2,box["y"]+box["height"]/2)
        page.wait_for_function("""()=>document.querySelector('input[aria-label="Selected task"]').value.startsWith('SYN-BRG-001-T013')""",timeout=30000)
        expected=set(data.task_elements(data.select(bundle,"SYN-BRG-001","V0","as_provided"),"SYN-BRG-001-T013"))
        def highlighted():
            return set(page.locator('.js-plotly-plot').nth(1).evaluate("el=>el.data[el.data.length-1].customdata.map(r=>r[0])"))
        page.wait_for_function("""()=>document.querySelectorAll('.js-plotly-plot')[0].data[0].marker.color[12]==='#F1AE32'""")
        assert highlighted()==expected
        page.locator('[data-testid="stMain"]').evaluate("el=>el.scrollTo({top:0,behavior:'instant'})")
        page.wait_for_function("()=>document.querySelector('[data-testid=stMain]').scrollTop===0")
        page.mouse.move(10,10)
        page.screenshot(path=str(out/"bridge_v0_as_provided.png"),full_page=True)
        choose("Project","SYN-BLD-001")
        ready("SYN-BLD-001")
        choose("Representation","Derived | synthetic computed dates")
        page.get_by_text("Derived dates are dependency-compliant synthetic calculations.",exact=False).wait_for()
        ready("SYN-BLD-001","derived")
        # GlobalId inspector deliberately selects a task other than the initial task.
        selected=data.select(bundle,"SYN-BLD-001","V0","derived")
        tid="SYN-BLD-001-T027";gid=data.task_elements(selected,tid)[0]
        choose("Inspect IFC element (GlobalId)",gid)
        page.wait_for_function("""tid=>document.querySelector('input[aria-label="Selected task"]').value.startsWith(tid)""",arg=tid)
        page.wait_for_function("""()=>document.querySelectorAll('.js-plotly-plot')[0].data[0].marker.color[26]==='#F1AE32'""")
        assert highlighted()==set(data.task_elements(selected,tid))
        page.locator('[data-testid="stMain"]').evaluate("el=>el.scrollTo({top:0,behavior:'instant'})")
        page.wait_for_function("()=>document.querySelector('[data-testid=stMain]').scrollTop===0")
        page.mouse.move(10,10)
        page.screenshot(path=str(out/"building_v0_derived.png"),full_page=True)
        progress=page.get_by_label("Synthetic progress layer | source calendar",exact=True)
        progress.focus()
        progress.press("Space")
        page.get_by_text("Purple diamonds:",exact=False).wait_for()
        page.wait_for_function("""()=>document.querySelectorAll('.js-plotly-plot')[0].data.some(d=>d.name.startsWith('Synthetic progress'))""")
        page.locator('[data-testid="stMain"]').evaluate("el=>el.scrollTo({top:0,behavior:'instant'})")
        page.wait_for_function("()=>document.querySelector('[data-testid=stMain]').scrollTop===0")
        page.mouse.move(10,10)
        page.screenshot(path=str(out/"building_synthetic_progress.png"),full_page=True)
        # Also inspect a different snapshot in the actual browser.
        choose("Snapshot","V2")
        page.wait_for_function("""()=>document.querySelectorAll('.js-plotly-plot')[0].data[0].customdata[0][12]==='SYN-BLD-001-V2'""")
        assert page.locator('[data-testid="stException"]').count()==0
        page.get_by_role("heading",name="Dependency validation",exact=False).evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
        page.mouse.move(10,10)
        page.screenshot(path=str(out/"building_v2_conflicts.png"),full_page=True)
        result=dict(gantt_pointer_selection=True,task_to_geometry_highlights=True,
                    globalid_selector_to_task=True,direct_mesh_click_selection=False,
                    project_switch=True,snapshot_switch=True,representation_switch=True,
                    synthetic_progress_layer=True,browser="Microsoft Edge / Playwright",screenshots=4)
        (out/"browser_validation.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        browser.close()
        return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default="http://localhost:8511")
    parser.add_argument("--out",type=Path,default=ROOT/"research/ifc4d/screenshots/stage3_8c")
    args=parser.parse_args()
    print(json.dumps(capture(args.url,args.out),indent=2))
