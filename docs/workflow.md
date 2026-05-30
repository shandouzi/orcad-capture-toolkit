# Main Workflow Guide

This document describes the complete workflow for cross-board connector net verification.

## Overview

This workflow verifies net name consistency between corresponding pins of mating connectors on two boards. A typical scenario: Board A's connector J1 mates with Board B's connector J1 — verify that the net names on corresponding pins match.

## Prerequisites

### 1. Prepare the Connector Pin Mapping Table

Create `connector_pin_map.csv` defining the pin mating relationship between the two board connectors:

```csv
ConnectorPin,Row,Col,MatingPin,MatingRow,MatingCol
A3,A,3,L3,L,3
A4,A,4,L4,L,4
...
```

- `ConnectorPin`: Pin number on Board A's connector
- `MatingPin`: Corresponding pin number on Board B's connector
- `Row`/`Col`: Physical position of the pin (used for visualization)

For mating connectors of the same type, the pairing is typically row-symmetric: A↔L, B↔K, C↔J, D↔H, E↔G, F↔F.

### 2. Confirm OrCAD Environment

- OrCAD Capture CIS 17.2+ installed
- DSN files for both boards opened in Capture

## Step 1: Extract Pin-Net Data

Run data extraction in OrCAD Capture for each board separately.

### 1.1 Extract Board A Data

```
1. Open Board A's DSN file in Capture
2. In the Command Window, enter: set targetRefDes "J1"
3. Press Enter
4. Enter: source ./scripts/get_component_nets.tcl
5. Press Enter
6. Output file: board_a_J1_pin_nets.csv
```

### 1.2 Extract Board B Data

```
1. Open Board B's DSN file in Capture
2. In the Command Window, enter: set targetRefDes "J1"
3. Press Enter
4. Enter: source ./scripts/get_component_nets.tcl
5. Press Enter
6. Output file: board_b_J1_pin_nets.csv
```

### 1.3 Output Format

Both CSV files share the same column structure:

| Column | Description |
|--------|-------------|
| RefDes | Component reference designator |
| PartValue | Component value / model |
| PinNumber | Pin number |
| PinName | Pin name |
| NetName | Net name |
| PagePath | Hierarchy path |

### Notes

- Leave `targetRefDes` empty to export all components (slower for large designs)
- The script recursively traverses hierarchical designs, automatically entering sub-modules
- Console previews the first 20 rows for quick verification
- CSV files use UTF-8 BOM encoding

## Step 2: Net Comparison

Run the comparison script from a Windows command line.

### 2.1 Run Command

```
py scripts/match_nets_interactive.py
```

### 2.2 Select Files

The script opens a GUI dialog (falls back to CLI mode if no GUI available). Select in order:

1. Board A's `pin_nets.csv`
2. Board B's `pin_nets.csv`
3. `connector_pin_map.csv`

### 2.3 Output Files

| File | Description |
|------|-------------|
| `match_report_<A>_vs_<B>.csv` | Match report in CSV format |
| `match_report_<A>_vs_<B>.xlsx` | Excel format with MISMATCH rows highlighted in yellow |

### 2.4 Match Status Descriptions

| Status | Meaning | Needs Attention |
|--------|---------|----------------|
| OK | Net names match exactly | No |
| MISMATCH | Net names differ | **Yes** |
| NC | Both sides empty (unconnected) | Depends |
| NC_A | Only side A is empty | **Yes** |
| NC_B | Only side B is empty | **Yes** |
| MISSING | Pin not found in mapping table | **Yes** |

### 2.5 Notes

- Net name comparison is strict string matching. Naming convention differences (e.g., `VCC_3V3` vs `VCC_3V3_MODULE`) are treated as MISMATCH.
- Matching is based on PinNumber + mapping table, not PinName.
- Source files are backed up once as `.bak`.
- Console output includes MISMATCH details for quick problem identification.

## Step 3 (Optional): Visual Review

### 3.1 Specific Visualization (Fixed Layout)

```
py scripts/generate_visualization.py
```

For specific connectors like the Molex 209311-1115 (688-pin).

### 3.2 Universal Visualization (Any Connector)

```
py scripts/generate_universal_viz.py
```

Select the match report CSV and pin map CSV. Supports top-bottom / left-right layout direction selection.

### 3.3 Visualization Features

- Hover over pin to show details
- Click pin to highlight mating pin
- Color coding: green=OK, red=MISMATCH, gray=NC, blue=MISSING
- Top status badge bar showing category counts
- Single self-contained HTML file, no server required

## Troubleshooting

### Too Many MISMATCH Results

1. Check for naming convention differences (e.g., module prefix/suffix differences)
2. Verify the pin mapping table is correct
3. Confirm both boards use the same connector model

### MISSING Pins

1. Check if the pin mapping table covers all pins
2. Confirm `targetRefDes` specifies the correct connector reference designator

### Empty Net Names

1. Confirm the pin is actually connected to a net in the schematic
2. Check cross-page connections in hierarchical designs
3. Confirm the pin is not an NC (No Connect) pin
