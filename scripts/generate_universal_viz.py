import csv
import json
import os
import sys
# design by shandouzi

try:
    from tkinter import Tk, filedialog, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False


def read_pin_map(pin_map_path):
    layout_a = {}
    layout_b = {}
    mating = {}
    with open(pin_map_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cp = row["ConnectorPin"].strip()
            cr = row["Row"].strip()
            cc = int(row["Col"].strip())
            mp = row["MatingPin"].strip()
            mr = row["MatingRow"].strip()
            mc = int(row["MatingCol"].strip())
            layout_a[cp] = {"row": cr, "col": cc}
            layout_b[mp] = {"row": mr, "col": mc}
            mating[cp] = mp
    return layout_a, layout_b, mating


def compute_grid(layout):
    row_set = set()
    col_set = set()
    row_cols = {}
    for pin, pos in layout.items():
        r = pos["row"]
        c = pos["col"]
        row_set.add(r)
        col_set.add(c)
        row_cols.setdefault(r, set()).add(c)
    sorted_rows = sorted(row_set)
    sorted_cols = sorted(col_set)
    min_col = min(col_set) if col_set else 0
    max_col = max(col_set) if col_set else 0
    all_cols = list(range(min_col, max_col + 1))
    valid_cells = {}
    for pin, pos in layout.items():
        valid_cells[(pos["row"], pos["col"])] = pin
    return {
        "rows": sorted_rows,
        "all_cols": all_cols,
        "row_valid_cols": {r: sorted(row_cols.get(r, set())) for r in sorted_rows},
        "valid_cells": {f"{r},{c}": p for (r, c), p in valid_cells.items()},
    }


def read_match_report(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    return rows, fieldnames


def generate_html(rows, fieldnames, layout_a, layout_b, label_a, label_b, output_path, direction="vertical"):
    grid_a = compute_grid(layout_a)
    grid_b = compute_grid(layout_b)

    pin_col = fieldnames[0]
    name_col = fieldnames[1]
    net_col = fieldnames[2]
    mate_pin_col = fieldnames[3]
    mate_name_col = fieldnames[4]
    mate_net_col = fieldnames[5]
    status_col = fieldnames[6]

    board_a_data = {}
    board_b_data = {}
    stats = {}
    for r in rows:
        pa = r.get(pin_col, "")
        pb = r.get(mate_pin_col, "")
        st = r.get(status_col, "")
        stats[st] = stats.get(st, 0) + 1
        if pa:
            board_a_data[pa] = {
                "name": r.get(name_col, ""),
                "net": r.get(net_col, ""),
                "mate": pb,
                "mate_name": r.get(mate_name_col, ""),
                "mate_net": r.get(mate_net_col, ""),
                "status": st,
            }
        if pb:
            board_b_data[pb] = {
                "name": r.get(mate_name_col, ""),
                "net": r.get(mate_net_col, ""),
                "mate": pa,
                "mate_name": r.get(name_col, ""),
                "mate_net": r.get(net_col, ""),
                "status": st,
            }

    is_vertical = direction == "vertical"

    css_direction = ""
    css_boards = ""
    css_board_item = ""
    if is_vertical:
        css_direction = "flex-direction: column;"
        css_boards = "display: flex; flex-direction: column; align-items: center; gap: 6px;"
        css_board_item = ""
    else:
        css_direction = "flex-direction: row;"
        css_boards = "display: flex; flex-direction: row; align-items: center; gap: 20px; justify-content: center;"
        css_board_item = "flex-shrink: 0;"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Connector Net Match - {label_a} vs {label_b}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: #1a1a2e; color: #e0e0e0;
  font-family: 'Segoe UI', Consolas, monospace;
  padding: 20px; overflow-x: auto;
}}
h1 {{ text-align: center; color: #fff; margin-bottom: 5px; font-size: 20px; }}
h2 {{ color: #e0e0e0; font-size: 13px; margin: 10px 0 4px; text-align: center; }}
.subtitle {{ text-align: center; color: #aaa; margin-bottom: 12px; font-size: 12px; }}
.summary {{
  display: flex; justify-content: center; gap: 14px;
  margin-bottom: 16px; font-size: 12px; flex-wrap: wrap;
}}
.summary span {{ padding: 3px 10px; border-radius: 3px; color: #fff; }}
.boards {{ {css_boards} }}
.board {{ {css_board_item} }}
.grid-wrap {{ display: flex; justify-content: center; }}
.pin-grid {{
  display: inline-grid;
  gap: 1px;
}}
.pin-cell {{
  width: 13px; height: 13px; border-radius: 2px;
  cursor: pointer; transition: transform 0.1s;
}}
.pin-cell:hover {{ transform: scale(2); z-index: 10; }}
.pin-cell.empty {{ background: transparent; cursor: default; }}
.pin-cell.empty:hover {{ transform: none; }}
.pin-cell.hl {{ outline: 2px solid #fff; z-index: 20; transform: scale(2); }}
.rl, .cl {{ display: flex; align-items: center; justify-content: center; font-size: 8px; color: #666; }}
.cl {{ height: 13px; }}
.divider {{
  width: 70%; max-width: 880px; margin: 6px auto;
  height: 2px; background: #444; position: relative;
}}
.divider-v {{
  width: 2px; min-height: 200px; background: #444;
  position: relative; align-self: center;
}}
.legend {{
  display: flex; justify-content: center; gap: 14px;
  margin-top: 14px; font-size: 11px;
}}
.legend-item {{ display: flex; align-items: center; gap: 3px; }}
.legend-color {{ width: 13px; height: 13px; border-radius: 2px; }}
#tooltip {{
  display: none; position: fixed; background: #2d2d44;
  border: 1px solid #555; padding: 7px 10px; border-radius: 4px;
  font-size: 10px; z-index: 100; pointer-events: none;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5); white-space: nowrap;
}}
#tooltip .tp {{ color: #fff; font-weight: bold; }}
#tooltip .tn {{ color: #81C784; }}
#tooltip .tm {{ color: #aaa; }}
#info-panel {{
  position: fixed; bottom: 0; left: 0; right: 0;
  background: #252540; border-top: 1px solid #444;
  padding: 10px 20px; display: none; z-index: 50;
  font-size: 12px;
}}
#info-panel .ip-title {{ color: #fff; font-weight: bold; font-size: 14px; margin-bottom: 6px; }}
#info-panel .ip-side {{ display: inline-block; width: 48%; vertical-align: top; }}
#info-panel .ip-label {{ color: #888; font-size: 10px; }}
#info-panel .ip-val {{ color: #e0e0e0; }}
#info-panel .ip-net {{ color: #81C784; font-weight: bold; }}
#info-panel .ip-close {{ position: absolute; top: 8px; right: 16px; cursor: pointer; color: #888; font-size: 16px; }}
#info-panel .ip-close:hover {{ color: #fff; }}
#info-panel .ip-status {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; color: #fff; }}
</style>
</head>
<body>
<h1>Connector Net Match Visualization</h1>
<div class="subtitle">{label_a} &lt;--&gt; {label_b}</div>
<div class="summary" id="summary"></div>
<div class="boards">
  <div class="board">
    <h2>{label_a}</h2>
    <div class="grid-wrap"><div class="pin-grid" id="ga"></div></div>
  </div>
  <div class="{'divider' if is_vertical else 'divider-v'}"></div>
  <div class="board">
    <h2>{label_b}</h2>
    <div class="grid-wrap"><div class="pin-grid" id="gb"></div></div>
  </div>
</div>
<div class="legend">
  <div class="legend-item"><div class="legend-color" style="background:#4CAF50"></div>OK</div>
  <div class="legend-item"><div class="legend-color" style="background:#F44336"></div>MISMATCH</div>
  <div class="legend-item"><div class="legend-color" style="background:#757575"></div>NC</div>
  <div class="legend-item"><div class="legend-color" style="background:#2196F3"></div>MISSING</div>
</div>
<div id="tooltip"></div>
<div id="info-panel">
  <span class="ip-close" id="ip-close">&times;</span>
  <div class="ip-title" id="ip-title"></div>
  <div class="ip-side" id="ip-side-a"></div>
  <div class="ip-side" id="ip-side-b"></div>
</div>
<script>
const GA={json.dumps(grid_a)};
const GB={json.dumps(grid_b)};
const DA={json.dumps(board_a_data)};
const DB={json.dumps(board_b_data)};
const ST={json.dumps(stats)};
const SC={{"OK":"#4CAF50","MISMATCH":"#F44336","NC":"#757575","NC_A":"#9E9E9E","NC_B":"#9E9E9E","MISSING":"#2196F3"}};
const LB={{"OK":"OK","MISMATCH":"MISMATCH","NC":"NC","NC_A":"NC(A)","NC_B":"NC(B)","MISSING":"MISSING"}};
const LA="{label_a}";
const LBL="{label_b}";

const sm=document.getElementById('summary');
for(const[k,v]of Object.entries(ST)){{if(v>0){{const s=document.createElement('span');s.style.background=SC[k]||'#666';s.textContent=LB[k]+': '+v;sm.appendChild(s);}}}}

function build(id,grid,data){{
  const el=document.getElementById(id);
  const rows=grid.rows;
  const allCols=grid.all_cols;
  const rowVC=grid.row_valid_cols;
  const cells=grid.valid_cells;

  const colCount=allCols.length;
  el.style.gridTemplateColumns='26px '+'repeat('+colCount+',13px)';

  el.appendChild(Object.assign(document.createElement('div'),{{className:'rl'}}));
  for(const c of allCols)el.appendChild(Object.assign(document.createElement('div'),{{className:'cl',textContent:c%10===0?c:''}}));

  for(const row of rows){{
    el.appendChild(Object.assign(document.createElement('div'),{{className:'rl',textContent:row}}));
    const vc=new Set(rowVC[row]||[]);
    for(const c of allCols){{
      const cell=document.createElement('div');cell.className='pin-cell';
      if(!vc.has(c)){{cell.classList.add('empty');el.appendChild(cell);continue;}}
      const pin=cells[row+','+c]||(row+c);
      const d=data[pin];
      if(d){{
        cell.style.background=SC[d.status]||'#444';
        cell.dataset.pin=pin;cell.dataset.nm=d.name;cell.dataset.net=d.net;
        cell.dataset.mate=d.mate;cell.dataset.mn=d.mate_name;cell.dataset.mnet=d.mate_net;
        cell.dataset.st=d.status;cell.dataset.bd=id;
        cell.addEventListener('mouseenter',showTT);
        cell.addEventListener('mouseleave',hideTT);
        cell.addEventListener('click',showInfo);
      }}else{{
        cell.style.background='#2a2a3e';
      }}
      el.appendChild(cell);
    }}
  }}
}}

const tt=document.getElementById('tooltip');
const ip=document.getElementById('info-panel');
let hlEls=[];

function showTT(e){{
  const d=e.target.dataset;if(!d.pin)return;
  tt.innerHTML='<div class="tp">'+d.pin+'</div><div>Name: '+d.nm+'</div><div class="tn">Net: '+(d.net||'(empty)')+'</div><div class="tm">Mate: '+d.mate+'</div><div>Status: '+d.st+'</div>';
  tt.style.display='block';tt.style.left=(e.clientX+14)+'px';tt.style.top=(e.clientY+14)+'px';
}}
function hideTT(){{tt.style.display='none';}}

function showInfo(e){{
  hlEls.forEach(x=>x.classList.remove('hl'));hlEls=[];
  const d=e.target.dataset;if(!d.pin)return;
  e.target.classList.add('hl');hlEls.push(e.target);
  const bd=d.bd;
  let pinA,nameA,netA,pinB,nameB,netB,status;
  if(bd==='ga'){{
    pinA=d.pin;nameA=d.nm;netA=d.net;pinB=d.mate;nameB=d.mn;netB=d.mnet;status=d.st;
    if(pinB){{const me=document.getElementById('gb').querySelector('[data-pin="'+pinB+'"]');if(me){{me.classList.add('hl');hlEls.push(me);}}}}
  }}else{{
    pinB=d.pin;nameB=d.nm;netB=d.net;pinA=d.mate;nameA=d.mn;netA=d.mnet;status=d.st;
    if(pinA){{const me=document.getElementById('ga').querySelector('[data-pin="'+pinA+'"]');if(me){{me.classList.add('hl');hlEls.push(me);}}}}
  }}
  const sc=SC[status]||'#666';
  document.getElementById('ip-title').innerHTML=pinA+' &harr; '+pinB+' <span class="ip-status" style="background:'+sc+'">'+status+'</span>';
  document.getElementById('ip-side-a').innerHTML='<div class="ip-label">'+LA+'</div><div class="ip-val">Pin: '+pinA+'</div><div class="ip-val">Name: '+nameA+'</div><div class="ip-net">Net: '+(netA||'(empty)')+'</div>';
  document.getElementById('ip-side-b').innerHTML='<div class="ip-label">'+LBL+'</div><div class="ip-val">Pin: '+pinB+'</div><div class="ip-val">Name: '+nameB+'</div><div class="ip-net">Net: '+(netB||'(empty)')+'</div>';
  ip.style.display='block';
}}

document.getElementById('ip-close').onclick=function(){{ip.style.display='none';hlEls.forEach(x=>x.classList.remove('hl'));hlEls=[];}};

build('ga',GA,DA);build('gb',GB,DB);
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML: {output_path} ({os.path.getsize(output_path)} bytes)")


def select_files_gui():
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    print("Step 1/4: Select match report CSV")
    csv_path = filedialog.askopenfilename(
        title="Select Match Report CSV",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    if not csv_path:
        print("  Cancelled.")
        sys.exit(0)
    print(f"  {csv_path}")

    print("Step 2/4: Select connector pin-map CSV")
    pin_map_path = filedialog.askopenfilename(
        title="Select Connector Pin-Map CSV",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    if not pin_map_path:
        print("  Cancelled.")
        sys.exit(0)
    print(f"  {pin_map_path}")

    print("Step 3/4: Select output HTML location")
    html_path = filedialog.asksaveasfilename(
        title="Save HTML Visualization As",
        defaultextension=".html",
        filetypes=[("HTML files", "*.html")],
        initialfile=os.path.splitext(os.path.basename(csv_path))[0] + ".html",
    )
    if not html_path:
        print("  Cancelled.")
        sys.exit(0)
    print(f"  {html_path}")

    print("Step 4/4: Choose layout direction")
    print("  1 = Vertical (top/bottom, default)")
    print("  2 = Horizontal (left/right)")
    direction = "vertical"
    try:
        from tkinter import simpledialog
        choice = simpledialog.askstring("Layout Direction", "1 = Vertical (top/bottom)\n2 = Horizontal (left/right)\n\nEnter 1 or 2:", parent=root)
        if choice and choice.strip() == "2":
            direction = "horizontal"
    except Exception:
        pass
    print(f"  Direction: {direction}")

    root.destroy()
    return csv_path, pin_map_path, html_path, direction


def select_files_cli():
    csv_path = input("  [1] Match report CSV path: ").strip().strip('"')
    if not os.path.isfile(csv_path):
        print(f"  ERROR: File not found: {csv_path}")
        sys.exit(1)

    pin_map_path = input("  [2] Connector pin-map CSV path: ").strip().strip('"')
    if not os.path.isfile(pin_map_path):
        print(f"  ERROR: File not found: {pin_map_path}")
        sys.exit(1)

    html_path = input("  [3] Output HTML path (blank for auto): ").strip().strip('"')
    if not html_path:
        html_path = os.path.splitext(csv_path)[0] + ".html"

    direction = input("  [4] Layout direction (1=vertical, 2=horizontal) [1]: ").strip()
    direction = "horizontal" if direction == "2" else "vertical"

    return csv_path, pin_map_path, html_path, direction


def main():
    print("=" * 50)
    print("  Universal Connector Net Visualization")
    print("  design by shandouzi")
    print("=" * 50)

    if HAS_TK:
        print("\nOpening file dialogs ...\n")
        csv_path, pin_map_path, html_path, direction = select_files_gui()
    else:
        csv_path, pin_map_path, html_path, direction = select_files_cli()

    print()
    print("Reading pin map ...")
    layout_a, layout_b, mating = read_pin_map(pin_map_path)
    print(f"  Board-A pins: {len(layout_a)}")
    print(f"  Board-B pins: {len(layout_b)}")

    print("Reading match report ...")
    rows, fieldnames = read_match_report(csv_path)
    pin_col = fieldnames[0]
    mate_pin_col = fieldnames[3]
    label_a = pin_col.replace("_PinNumber", "")
    label_b = mate_pin_col.replace("_PinNumber", "")
    print(f"  {label_a} <-> {label_b}")
    print(f"  Rows: {len(rows)}")

    print(f"Generating HTML ({direction}) ...")
    generate_html(rows, fieldnames, layout_a, layout_b, label_a, label_b, html_path, direction)
    print("\nDone. Open the HTML file in your browser.")


if __name__ == "__main__":
    main()
