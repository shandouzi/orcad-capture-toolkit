# OrCAD Capture Automation Toolkit

A TCL + Python automation toolkit for OrCAD Capture CIS 17.2. Designed for schematic data extraction, cross-board connector net verification, OLB library pin inspection, hierarchical design page mapping, and interactive visualization.

> ## Background
>
> This toolkit was originally developed to meet a real-world need: **verifying the pin-level net name consistency between OAM (OAM Module) and UBB (UBB Board) interconnected via board-to-board connectors**. The project required validating that every corresponding pin on both sides of the connector carried matching net names, which led to the incremental development of a complete pipeline — from data extraction and net comparison to interactive visualization.
>
> While some design choices (e.g., connector pin mappings, topology discovery algorithms) still reflect the OAM/UBB use case, the core functionality is fully generalizable and can be extended to connector net verification between any pair of boards. Users can adapt configuration files and script parameters to their own connector models, pin arrangements, and naming conventions.
>
> I am relatively new to Cadence automation. This repository serves as a record of my learning journey and a way to share with the community. Issues and pull requests are very welcome.

## Scripts Overview

| Script | Language | Description |
|--------|----------|-------------|
| `get_olb_pins.tcl` | TCL | Extract pin info from OLB libraries for packaging validation |
| `get_page_mapping.tcl` | TCL | Export global page number to page name mapping for hierarchical designs |
| `get_component_nets.tcl` | TCL | Extract pin-to-net data for specified component refdes (CSV) |
| `match_nets_interactive.py` | Python | Cross-board connector net comparison with match report generation |
| `generate_visualization.py` | Python | Generate per-pin interactive HTML visualization (specific connector layout) |
| `generate_universal_viz.py` | Python | Universal connector visualization (auto-inferred layout from pin map) |
| `discover_oam_topology.py` | Python | Auto-discover interconnect topology via AC coupling capacitor tracing |

## Use Cases

- Net name consistency verification for board-to-board connector mating
- OLB component package pin definition validation
- Hierarchical schematic global page directory export
- Pin-to-net mapping export for any component from a schematic
- Connector interconnect topology auto-discovery and visualization

## Requirements

| Component | Requirement |
|-----------|-------------|
| OrCAD Capture CIS | 17.2+ (TCL scripts run inside Capture Command Window) |
| Python | 3.x |
| Python dependency | `openpyxl` (`pip install openpyxl`) |
| OS | Windows |
| Python launcher | Use `py` command |

## Quick Start

### 1. OLB Library Pin Inspection

Open an OLB file in Capture Library Editor, then run:

```tcl
source ./scripts/get_olb_pins.tcl
```

Output: `olb_pin_info.csv`, `olb_pin_info_detail.csv`

### 2. Design Page Directory Export

Open a DSN file in Capture Design mode, then run:

```tcl
source ./scripts/get_page_mapping.tcl
```

Output: `page_mapping.csv`

### 3. Component Pin-Net Data Extraction

```tcl
set targetRefDes "J1"
source ./scripts/get_component_nets.tcl
```

Output: `<design_name>_<RefDes>_pin_nets.csv`

### 4. Cross-Board Net Comparison

```
py scripts/match_nets_interactive.py
```

A GUI dialog will prompt you to select two CSV files and the pin mapping table. Outputs a match report (CSV + XLSX).

### 5. Visualization

```
py scripts/generate_universal_viz.py
```

Select the match report CSV and pin map CSV to generate an interactive HTML visualization.

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Standalone Tools (anytime)                  │
│                                                             │
│  ┌──────────────────────┐    ┌──────────────────────────┐   │
│  │ get_olb_pins.tcl     │    │ get_page_mapping.tcl     │   │
│  │ OLB ──> Pin Info CSV │    │ DSN ──> Page Dir CSV     │   │
│  └──────────────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               Main Workflow (sequential)                     │
│                                                             │
│  Step 1: Data Extraction (run in OrCAD, once per board)     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  get_component_nets.tcl                              │   │
│  │                                                      │   │
│  │  DSN (Board-A) ──> board_a_J1_pin_nets.csv           │   │
│  │  DSN (Board-B) ──> board_b_J1_pin_nets.csv           │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│  Step 2: Net Comparison (Windows command line)              │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  match_nets_interactive.py                           │   │
│  │                                                      │   │
│  │  Board-A CSV ──┐                                     │   │
│  │  Board-B CSV ──┼──> match_report.csv / .xlsx         │   │
│  │  pin_map.csv ──┘                                     │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│  Step 3 (optional): Visual Review                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  generate_visualization.py     (specific layout)     │   │
│  │  generate_universal_viz.py     (universal layout)    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Script Details

### get_olb_pins.tcl

Extracts complete pin information for all components from an open OLB library.

**Prerequisite:** OLB file open in Capture Library Editor

**Output:**
- `<libname>_pin_info.csv` — Raw data sorted by section, easy to filter/sort in Excel
- `<libname>_pin_info_detail.csv` — With section headers and summaries

**CSV Columns:**

| Column | Description | Example |
|--------|-------------|---------|
| PartName | Component name | GTL2003PW |
| PartRef | Reference designator prefix | U |
| Section | Section number | 1, 2, 3... |
| View | Symbol view | Normal / Convert |
| PinIndex | Pin order index | 0, 1, 2... |
| PinName | Pin name | GND, S1, D1 |
| PinNumber | Pin number | 1, NAG62, NP47 |
| PinPosition | Pin position | 0, 1, 2... |
| PinType(Enum) | Pin type (enum) | Power, Input, Passive |
| PinType(Semantic) | Pin type (semantic) | Power, Passive |
| Package | Package name | GTL2003PW |

**Key Features:**
- Extracts PinType from both enum value and semantic string (they may differ)
- Supports multi-section components with correct Device-to-Part matching via Cell name
- Section numbers follow Package Device order (not arbitrary OLB storage order)
- Output files are named after the OLB filename automatically
- CSV output sorted by Package → Section → Pin index

---

### get_page_mapping.tcl

Extracts global page number to page name mapping from an open DSN design.

**Prerequisite:** DSN file open in Capture Design mode

**Output:**
- `page_mapping.csv` — Columns: `GlobalPage, LocalPage, LocalTotal, PageName, Module`

**Key Features:**
- Uses `DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder` for correct title block ordering
- Extracts both global index and per-module local page number/count
- Auto-strips letter prefix from page names
- Extracts module name from title block
- Handles multi-level hierarchical designs

---

### get_component_nets.tcl

Extracts pin-to-net mapping for a specified component refdes from an open DSN design. Run once per board.

**Prerequisite:** DSN file open in Capture Design mode

**Usage:**

```tcl
; Set target refdes in Command Window first
set targetRefDes "J1"
; Then run the script
source ./scripts/get_component_nets.tcl
```

Leave `targetRefDes` empty to export all components.

**Output:**
- `<design_name>_<RefDes>_pin_nets.csv` — Columns: `RefDes, PartValue, PinNumber, PinName, NetName, PagePath`

**Key Features:**
- Recursively traverses hierarchical schematics
- Auto-extracts design name for output filename
- Console preview of first 20 rows
- Lists discovered refdes when target is not found
- Dual-path net name retrieval (via Net and Wire objects)

---

### match_nets_interactive.py

Matches connector pin nets between two boards using a physical pin mapping table, generating a comparison report.

**Dependency:** `pip install openpyxl`

**Input Files:**

| File | Required Columns | Source |
|------|-----------------|--------|
| Board-A pin-net CSV | `PinNumber, PinName, NetName` | `get_component_nets.tcl` |
| Board-B pin-net CSV | `PinNumber, PinName, NetName` | `get_component_nets.tcl` |
| Connector pin map CSV | `ConnectorPin, MatingPin` | `config/connector_pin_map.csv` |

**Output:**
- `match_report_<tagA>_vs_<tagB>.csv`
- `match_report_<tagA>_vs_<tagB>.xlsx` (MISMATCH rows highlighted in yellow)

**Match Statuses:**

| Status | Condition |
|--------|-----------|
| OK | Net names match on both sides |
| MISMATCH | Net names differ |
| NC | Both sides are empty |
| NC_A | Side A empty, side B non-empty |
| NC_B | Side A non-empty, side B empty |
| MISSING | Pin not found in mapping table |

---

### generate_visualization.py

Generates an interactive HTML visualization from a match report. Designed specifically for the Molex 209311-1115 (688-pin) connector layout.

**Output:** Single self-contained HTML file (all CSS + JS embedded)

**Interactive Features:**
- Hover to show pin details
- Click pin to highlight mating pin
- Color coding: green=OK, red=MISMATCH, gray=NC, blue=MISSING
- Board-B displayed in mirrored row order (reflecting physical mating direction)

---

### generate_universal_viz.py

Universal visualization tool. Auto-infers connector row/column layout from `connector_pin_map.csv`, supporting any connector type.

**Additional Input:** Pin map CSV must include `Row, Col, MatingRow, MatingCol` columns

**Comparison with generate_visualization.py:**

| Aspect | generate_visualization.py | generate_universal_viz.py |
|--------|--------------------------|---------------------------|
| Connector layout | Hardcoded 688 pins | Auto-inferred from CSV |
| Scope | Specific connector | Any connector |
| Layout direction | Top-bottom only | Top-bottom / left-right selectable |

---

### discover_oam_topology.py

Auto-discovers connector interconnect topology from full pin-net CSV data via AC coupling capacitor tracing.

**Usage:**

```
py scripts/discover_oam_topology.py <pin_nets_csv> --connectors J1 J2 ... K8 --output-dir <dir>
```

**Output:**
- `topology_report.html` — Interactive ring network diagram + detail table
- `topology_pair_detail.csv` — Details grouped by connector pair
- `topology_detail.csv` — Full topology links

**Key Features:**
- Topology discovery does not depend on net name naming conventions — relies solely on NetName uniqueness matching
- Auto-identifies AC coupling capacitors (prefix C + 2 pins + both sides have connector pins)
- Natural sorting (differential pairs _P/_N kept adjacent)
- Red highlighting for net name number mismatches

## Known Limitations

- OrCAD 17.2 TCL API **does not support net name write operations** (all Set methods fail silently). SPB 23.1+ may support this.
- TCL scripts must run inside the Capture Command Window; they cannot be executed standalone.
- CSV reading uses UTF-8 BOM encoding (OrCAD exports may use gb2312; Python scripts handle multi-encoding fallback).
- Windows only.

## Configuration

### connector_pin_map.csv

Physical pin mating map for board-to-board connectors. Defines the pin-to-pin pairing relationship for mating connectors.

**Format:**
```csv
ConnectorPin,Row,Col,MatingPin,MatingRow,MatingCol
A3,A,3,L3,L,3
A4,A,4,L4,L,4
```

**Properties:**
- Encoding: UTF-8 with BOM
- Mating pairs: A-L, B-K, C-J, D-H, E-G, F-F
- Shared input for `match_nets_interactive.py` and `generate_universal_viz.py`

## Documentation

| Document | Description |
|----------|-------------|
| [API Reference](docs/api_reference.md) | OrCAD Capture TCL Dbo API usage reference |
| [Pitfalls](docs/pitfalls.md) | Common traps and solutions in Cadence TCL development |
| [Workflow](docs/workflow.md) | Detailed step-by-step main workflow guide |

## License

MIT License
