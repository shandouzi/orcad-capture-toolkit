# Cadence OrCAD TCL Development Pitfalls

This document compiles all traps and workarounds encountered during the development of OrCAD Capture CIS 17.2 TCL scripts.

---

## Pitfall 1: Iterator Return Values Cause `invalid command name "0"`

**Symptom:**

```tcl
set lPart [$lPIter NextPartInst $lStatus]
; => invalid command name "0"
```

**Root cause:** Cadence SWIG bindings return multiple values from methods. The status code `0` gets misinterpreted by Tcl as a command name.

**Solution:**

```tcl
set res [list]
catch { set res [$lPIter NextPartInst $lStatus] }
set lPart [lindex $res 0]
```

**Applies to:** `NextPage`, `NextPartInst`, `NextPin`, `NextDevice`, `NextPart`, `GetRootSchematic`, `GetContents`, `GetNet`, `GetWire`, `NewPagesIter`, `NewPartInstsIter`, `NewPinsIter`, `NewDevicesIter`, and virtually all SWIG methods.

---

## Pitfall 2: `GetName` vs `GetNetName`

**Symptom:** Calling `GetName` on DboNet returns an empty string.

```tcl
$lNet GetName $cstr
DboTclHelper_sGetConstCharPtr $cstr  ; => '' (empty)
```

**Solution:** Use `GetNetName` instead.

```tcl
$lNet GetNetName $cstr
DboTclHelper_sGetConstCharPtr $cstr  ; => 'GND' (correct)
```

**Applies to:** Both `DboNet` and `DboWire` objects.

---

## Pitfall 3: CString Still Has Value After catch

**Symptom:** `GetPinName` is caught by `catch`, appearing to be an error, but the CString has been correctly filled.

```tcl
set cstr [DboTclHelper_sMakeCString]
catch { $lPin GetPinName $cstr }
; catch returns non-zero (captured DboState object)

DboTclHelper_sGetConstCharPtr $cstr  ; => 'VBAT' (has value!)
```

**Root cause:** In the SWIG binding, `GetPinName` returns multiple values (DboState + void). Tcl throws the DboState object as a return value, caught by `catch`. But the CString reference parameter has already been correctly written by the C++ layer.

**Conclusion:** Don't worry about catch return values — just check the CString content.

---

## Pitfall 4: `GetPageNumber` / `GetPageCount` Require `$lStatus`

**Symptom:** `GetPageNumber` always returns `0`.

**Root cause:** Missing `$lStatus` parameter. The SWIG binding does not raise an error but returns an incorrect value.

```tcl
; WRONG
$lTB GetPageNumber    ; => 0

; CORRECT
$lTB GetPageNumber $lStatus  ; => actual page number
```

**Impact:** `GetPageNumber`, `GetPageCount`, `GetPinType`, and similar methods all require `$lStatus`.

---

## Pitfall 5: Page Numbers Reset in Hierarchical Designs

**Symptom:** `GetPageNumber` returns page numbers that restart from 1 in child modules.

```
MAIN:       PageNumber 1-7,   PageCount 7
Module B:   PageNumber 1-7,   PageCount 7
Module P:   PageNumber 1-17,  PageCount 17
```

**Solution:** Use `DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder` to get a globally sorted page list. The position index is the global page number.

```tcl
set pageList [DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign]
set lIter    [DboRefDesUtils_NewListIter $pageList]
```

**Key:** Only needs `$lDesign` as parameter — no `$lStatus`.

---

## Pitfall 6: Global List Iterator Uses `hasNext`/`next` Pattern

**Symptom:** Trying to iterate a global list with the common Capture `NextXxx $lStatus` + NULL check pattern fails.

**Solution:** The iterator from `DboRefDesUtils_NewListIter` uses Java-style `hasNext`/`next`:

```tcl
; WRONG
$lIter NextPageStructOcc $lStatus

; CORRECT
while {[$lIter hasNext]} {
    set item  [$lIter next]
    set lPage [DboPageStructOcc_getPage $item]
}
```

---

## Pitfall 7: `NewPinsIter` vs `NewPinInstsIter`

**Symptom:** `NewPinInstsIter` returns NULL in Design mode.

**Solution:** Use `NewPinsIter` in Design mode:

```tcl
; WRONG (returns NULL in Design mode)
$partInst NewPinInstsIter $lStatus

; CORRECT
$partInst NewPinsIter $lStatus
```

**Reason:** Different pin object types:
- Design mode: `DboPortInst` — use `NewPinsIter`
- Library mode: `DboSymbolPin` — use `NewLPinsIter`

---

## Pitfall 8: `GetActivePMDesign` Returns NULL in Library Editor

**Symptom:** All Design-level APIs return NULL in the Library Editor window.

```tcl
set lDesign [GetActivePMDesign]  ; => NULL
set lLib [GetActiveLib]           ; => NULL
set lSession [GetSession]         ; => NULL
```

**Solution:** Use `GetActivePMLastLibrary` in Library Editor:

```tcl
set theLib [GetActivePMLastLibrary]  ; => _p_DboLib (success)
```

---

## Pitfall 9: No `GetPinNumber` Method on `DboSymbolPin`

**Symptom:** Cannot directly get pin numbers on Pin objects in Library mode.

**Root cause:** PinNumber belongs to the Package → Device level, not the Symbol Pin.

**Solution:** Get PinNumber indirectly through Package → Device → SemanticString:

```tcl
set pkg [$lPart GetPackagePtr]
set devIter [$pkg NewDevicesIter $lStatus]
set dev [$devIter NextDevice $lStatus]
$dev GetSemanticString $cstr
; Extract PinNumber(index) = value from the returned text via regex
```

**Note:** Multi-section components require iterating all Devices and merging PinNumber mappings.

---

## Pitfall 10: CSV Encoding Is Not UTF-8

**Symptom:** `UnicodeDecodeError` when reading OrCAD-exported CSV files.

**Root cause:** OrCAD Capture may export CSV files in gb2312 encoding.

**Solution:** Multi-encoding fallback:

```python
encodings = ["utf-8-sig", "utf-8", "gb2312", "gbk", "latin-1"]
for enc in encodings:
    try:
        with open(csv_path, "r", encoding=enc) as f:
            reader = csv.DictReader(f)
            # process data
        break
    except (UnicodeDecodeError, UnicodeError):
        continue
```

---

## Pitfall 11: OrCAD 17.2 Does Not Support NetName Write

**Symptom:** All Dbo-level Set operations fail silently (no error, but value unchanged).

Confirmed non-functional APIs:

| API | Behavior |
|---|---|
| `DboNet_SetName` | Fails silently |
| `DboSchematicNet_SetName` | Fails silently |
| `DboWireScalar_SetName` | Fails silently |
| `DboAlias_SetName` | Alias object not accessible |
| `PlaceNetAlias` | Interactive mode only; not usable from scripts |

**Conclusion:** OrCAD 17.2 TCL API only supports read operations. Net name writes are not supported. SPB 23.1+ may support this. To modify net names, use OrCAD Find & Replace or edit the DSN file directly (latter has corruption risk).

---

## Pitfall 12: Occurrence Paths All Return NULL

**Symptom:** The following APIs all return NULL:

```tcl
$lDesign GetFlatSchematic $lStatus           ; => NULL
$lDesign GetRootSchematicOccurrence $lStatus ; => NULL
$childSch GetOccurrence $lStatus             ; => NULL
```

**Conclusion:** Some designs do not support the Occurrence path. All operations must use the Schematic → Page → PartInst path.

---

## Pitfall 13: No Net Iterator on Page

**Symptom:** All Net iterators on Page return NULL:

```tcl
$page NewNetsIter $lStatus         ; => NULL
$page NewNetInstsIter $lStatus     ; => NULL
$page NewSignalNetsIter $lStatus   ; => NULL
```

**Solution:** Get Net objects through Pin → GetNet. Only `NewWiresIter` works on Page.

---

## Pitfall 14: `targetRefDes` Variable Overwritten by Script

**Symptom:** User sets `set targetRefDes "J1"` in Command Window, but it gets overwritten to empty after running the script.

**Solution:** Use `info exists` to detect:

```tcl
if {![info exists targetRefDes]} {
    set targetRefDes ""
}
```

---

## Pitfall 15: Commas in Field Values Break CSV Format

**Symptom:** PinName containing commas (e.g., `PC13/TAMPER,RTC`) causes CSV column misalignment.

**Solution:** Replace commas before writing to CSV:

```tcl
regsub -all {,} $field { } field
```

---

## Pitfall 16: Lexicographic Sort Scatters Differential Pairs

**Symptom:** Default sort order is `_N_0, _N_1, _N_10, _N_11, _N_2` instead of natural order.

**Solution:** Extract trailing digits and zero-pad:

```javascript
function netSortKey(net) {
    const m = net.match(/^(.*[._])(P|N)_(\d+)$/i);
    if (!m) return net;
    return m[1] + m[2].toUpperCase() + "_" + parseInt(m[3]).toString().padStart(3, '0');
}
```

---

## Pitfall 17: `DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder` Parameters

**Symptom:** Wrong parameters cause errors.

```tcl
; WRONG
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lRoot $lStatus   ; error
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign $lStatus ; error
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lRoot            ; error

; CORRECT — only $lDesign, single parameter
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign          ; success
```
