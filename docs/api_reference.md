# OrCAD Capture CIS 17.2 TCL Dbo API Reference

This document is distilled from hands-on debugging experience and covers commonly used Dbo TCL API calling patterns in OrCAD Capture CIS 17.2.

## Entry Objects

### Get Current Design (Design Mode)

```tcl
set lDesign [GetActivePMDesign]
```

Returns a `DboDesign` object. Must be called with a DSN design open.

### Get Current Library (Library Editor Mode)

```tcl
set theLib [GetActivePMLastLibrary]
```

Returns a `DboLib` object. Must be called in the Library Editor window.

**Note:** `GetActivePMDesign` and `GetActiveLib` both return NULL in Library Editor mode.

### State Object

```tcl
set lStatus [DboState]
```

Nearly all Dbo API calls require a `DboState` object as a parameter. Create it before using any other API.

---

## String System (Three-Step Pattern)

Cadence Dbo API string retrieval follows a consistent three-step pattern:

```tcl
; 1. Create a CString container
set cstr [DboTclHelper_sMakeCString]

; 2. API fills the CString
$obj GetName $cstr

; 3. Convert to Tcl string
set str [DboTclHelper_sGetConstCharPtr $cstr]
```

**Applies to:** `GetName`, `GetPinName`, `GetPinNumber`, `GetNetName`, `GetReferenceDesignator`, `GetPartValue`, `GetSchematicName`, and all other string-returning APIs.

**Note:** You cannot create a CString with `CString` directly, nor can you extract a string directly from an API return value. You must use `DboTclHelper_sMakeCString` and `DboTclHelper_sGetConstCharPtr`.

---

## SWIG Return Value Handling (catch + lindex Pattern)

In Cadence SWIG bindings, many methods return multiple values (including a DboState status code). Direct assignment causes an `invalid command name "0"` error.

**Always use the catch + lindex pattern:**

```tcl
; WRONG — causes "invalid command name "0""
set lPart [$lPIter NextPartInst $lStatus]

; CORRECT — catch + lindex to get the first return value
set res [list]
catch { set res [$lPIter NextPartInst $lStatus] }
set lPart [lindex $res 0]
```

**Applies to:** `GetRootSchematic`, `NextPage`, `NextPartInst`, `NextPin`, `NextDevice`, `GetContents`, `GetNet`, `GetWire`, `NewPagesIter`, `NewPartInstsIter`, `NewPinsIter`, `NewDevicesIter`, and virtually all SWIG-bound methods.

**Special case:** Some methods like `GetPinName`, `GetPinNumber` still correctly fill the CString even after catch captures a DboState object.

---

## Object Hierarchy

### Design Mode

```
DboDesign
  └── DboSchematic (Root)
        └── DboPage
              ├── DboTitleBlock
              └── DboPartInst
                    ├── Normal component → extract Pin-Net data
                    └── Hierarchy Block → DboView → DboSchematic (recurse)
```

### Library Mode

```
DboLib
  └── DboLibPart
        ├── DboSymbolPin (Normal / Convert view)
        └── DboPackage
              └── DboDevice
                    └── SemanticString (contains PinNumber mapping)
```

---

## Design Mode API

### Get Root Schematic

```tcl
set rootRes [list]
catch { set rootRes [$lDesign GetRootSchematic $lStatus] }
set lRootSch [lindex $rootRes 0]
```

### Iterate Pages (Local Order)

```tcl
set pageIterRes [list]
catch { set pageIterRes [$lSchematic NewPagesIter $lStatus] }
set lPageIter [lindex $pageIterRes 0]

while {$idx < 500} {
    set pgRes [list]
    catch { set pgRes [$lPageIter NextPage $lStatus] }
    set lPage [lindex $pgRes 0]
    if {$lPage == "" || $lPage == "NULL"} { break }
    ; process lPage...
    incr idx
}
```

**Note:** `NewPagesIter` returns pages in internal database order, not title block page number order.

### Iterate Pages (Global Title Block Order)

```tcl
set pageList [DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign]
set lIter    [DboRefDesUtils_NewListIter $pageList]

set globalIdx 0
while {[$lIter hasNext]} {
    set item  [$lIter next]
    set lPage [DboPageStructOcc_getPage $item]
    incr globalIdx
    ; globalIdx is the global page number
}
```

**Key points:**
- Only needs `$lDesign` as parameter — no `$lStatus` required
- The returned iterator uses `hasNext`/`next` pattern (not the common Capture `Next` pattern)
- Automatically handles hierarchical designs; child module pages are interleaved at the correct position

### Iterate PartInst

```tcl
set piRes [list]
catch { set piRes [$lPage NewPartInstsIter $lStatus] }
set lPIter [lindex $piRes 0]

while {$pc < 2000} {
    set pRes [list]
    catch { set pRes [$lPIter NextPartInst $lStatus] }
    set lPI [lindex $pRes 0]
    if {$lPI == "" || $lPI == "NULL"} { break }
    ; process lPI...
    incr pc
}
```

### Get Component Refdes and Value

```tcl
set refCS [DboTclHelper_sMakeCString]
catch { $lPI GetReferenceDesignator $refCS }
set refdes [DboTclHelper_sGetConstCharPtr $refCS]

set valCS [DboTclHelper_sMakeCString]
catch { $lPI GetPartValue $valCS }
set partValue [DboTclHelper_sGetConstCharPtr $valCS]
```

### Detect Hierarchy Block

```tcl
set cntRes [list]
catch { set cntRes [$lPI GetContents $lStatus] }
set lView [lindex $cntRes 0]

if {$lView != "" && $lView != "NULL"} {
    ; This is a Hierarchy Block
    set childSch [DboViewToDboSchematic $lView]
    ; Recurse into childSch
} else {
    ; This is a normal component
}
```

### Iterate Pins

```tcl
set pinsRes [list]
catch { set pinsRes [$lPI NewPinsIter $lStatus] }
set pinsIter [lindex $pinsRes 0]

while {$pinIdx < 1000} {
    set pinRes [list]
    catch { set pinRes [$pinsIter NextPin $lStatus] }
    set lPin [lindex $pinRes 0]
    if {$lPin == "" || $lPin == "NULL"} { break }
    ; process lPin...
    incr pinIdx
}
```

**Note:** Must use `NewPinsIter`, not `NewPinInstsIter`. The latter returns NULL in Design mode.

### Get Pin Attributes

```tcl
; Pin function name
set pnCS [DboTclHelper_sMakeCString]
catch { $lPin GetPinName $pnCS }
set pinName [DboTclHelper_sGetConstCharPtr $pnCS]

; Pin number
set pnumCS [DboTclHelper_sMakeCString]
catch { $lPin GetPinNumber $pnumCS }
set pinNumber [DboTclHelper_sGetConstCharPtr $pnumCS]

; Pin type (integer enum)
catch { set pinTypeNum [$lPin GetPinType $lStatus] }
```

Pin object type is `DboPortInst` (not `DboSymbolPin`, which is only available in Library mode).

### Get NetName (Most Critical)

**Primary path: via DboNet**

```tcl
set netRes [list]
catch { set netRes [$lPin GetNet $lStatus] }
set lNet [lindex $netRes 0]

if {$lNet != "" && $lNet != "NULL"} {
    set nnCS [DboTclHelper_sMakeCString]
    catch { $lNet GetNetName $nnCS }
    set netName [DboTclHelper_sGetConstCharPtr $nnCS]
}
```

**Fallback path: via DboWire**

```tcl
if {$netName == ""} {
    set wireRes [list]
    catch { set wireRes [$lPin GetWire $lStatus] }
    set lWire [lindex $wireRes 0]

    if {$lWire != "" && $lWire != "NULL"} {
        set wnCS [DboTclHelper_sMakeCString]
        catch { $lWire GetNetName $wnCS }
        set netName [DboTclHelper_sGetConstCharPtr $wnCS]
    }
}
```

**Critical:** Use `GetNetName`, not `GetName`. `GetName` on DboNet returns an empty string.

### TitleBlock Operations

```tcl
set lTBIter [$lPage NewTitleBlocksIter $lStatus]
set lTB [$lTBIter NextTitleBlock $lStatus]

if {$lTB != "NULL"} {
    ; Must pass $lStatus — otherwise returns 0
    set pageNum [$lTB GetPageNumber $lStatus]
    set pageCnt [$lTB GetPageCount $lStatus]

    ; Module name
    set schCStr [DboTclHelper_sMakeCString]
    catch { $lTB GetSchematicName $schCStr }
    set moduleName [DboTclHelper_sGetConstCharPtr $schCStr]

    ; Property read
    set propNameCStr [DboTclHelper_sMakeCString]
    set valCStr [DboTclHelper_sMakeCString]
    DboTclHelper_sSetCString $propNameCStr "Page Count"
    $lTB GetEffectivePropStringValue $propNameCStr $valCStr
    ; Note: "Page Count" returns global total pages, not local count
}
```

### EffectiveProp Property Names

| Property Name | Return Value | Note |
|---|---|---|
| `Page Number` | Local page number | Same as `GetPageNumber` |
| `Page Count` | Global total page count | Not the local value from `GetPageCount` |
| `PageNumber` | Empty | Case-sensitive |
| `page_number` | Empty | Case-sensitive |

---

## Library Mode API

### Iterate Parts

```tcl
set lPartIter [DboLib_NewPartsIter $theLib $lStatus]
while {1} {
    set partRes [list]
    catch { set partRes [$lPartIter NextPart $lStatus] }
    set lPart [lindex $partRes 0]
    if {$lPart == "" || $lPart == "NULL"} { break }
}
```

### Get Part Attributes

```tcl
$lPart GetReference $cstr            ; Reference prefix (U, R, C...)
$lPart GetPartValue $cstr            ; Part Value
$lPart GetName $cstr                 ; Full name (e.g., GTL2003PW.Normal)
$lPart GetContentsViewType $lStatus  ; View type (0=Normal, 1=Convert)
$lPart GetPackagePtr                 ; Get Package object
```

### Iterate Library Pins

```tcl
set lPinIter [$lPart NewLPinsIter $lStatus]
while {1} {
    set pinRes [list]
    catch { set pinRes [$lPinIter NextPin $lStatus] }
    set lPin [lindex $pinRes 0]
    if {$lPin == "" || $lPin == "NULL"} { break }
}
```

### Library Pin Attributes

```tcl
$lPin GetPinName $cstr          ; Pin name
$lPin GetPinType $lStatus       ; Pin type (integer enum)
$lPin GetSemanticString $cstr   ; Full semantic string
```

### Get PinNumber (via Package → Device)

```tcl
set pkg [$lPart GetPackagePtr]

set devIterRes [list]
catch { set devIterRes [$pkg NewDevicesIter $lStatus] }
set devIter [lindex $devIterRes 0]

while {1} {
    set devRes [list]
    catch { set devRes [$devIter NextDevice $lStatus] }
    set dev [lindex $devRes 0]
    if {$dev == "" || $dev == "NULL"} { break }

    set devSSCS [DboTclHelper_sMakeCString]
    catch { $dev GetSemanticString $devSSCS }
    set devSS [DboTclHelper_sGetConstCharPtr $devSSCS]
    ; Extract PinNumber(index) = value from devSS via regex
}
```

### SemanticString Parsing

`GetSemanticString` returns text containing complete attributes that can be parsed with regex:

```tcl
; Pin attributes
regexp {PinType = (\w+)} $semStr match pinType
regexp {PinPosition = (\d+)} $semStr match pinPosition

; Pin number mapping in Device
regexp {PinNumber\((\d+)\) = (\w+)} $devSS match idx val
```

---

## Enum Value Mappings

### PinType

| Enum | Meaning |
|------|---------|
| 0 | Open |
| 1 | Bidirectional |
| 2 | Output3State |
| 3 | Output |
| 4 | Input |
| 5 | OpenCollector |
| 6 | Passive |
| 7 | Power |
| 8 | Passive |
| 9 | HIZ |
| 10 | Short |
| 11 | Shorted |

---

## Unsupported APIs (OrCAD 17.2)

The following write operations all fail silently in OrCAD 17.2:

| API | Behavior |
|---|---|
| `DboNet_SetName` | Fails silently |
| `DboSchematicNet_SetName` | Fails silently |
| `DboWireScalar_SetName` | Fails silently |
| `DboAlias_SetName` | Alias object not accessible |
| `SetEffectivePropStringValue("Name", ...)` | No effect |

The following paths return NULL (Occurrence not supported):

| API | Returns |
|---|---|
| `$lDesign GetFlatSchematic $lStatus` | NULL |
| `$lDesign GetRootSchematicOccurrence $lStatus` | NULL |
| `$childSch GetOccurrence $lStatus` | NULL |

All Net iterators on Page return NULL — nets must be obtained via Pin → GetNet:

| API | Returns |
|---|---|
| `$page NewNetsIter $lStatus` | NULL |
| `$page NewNetInstsIter $lStatus` | NULL |
| `$page NewSignalNetsIter $lStatus` | NULL |
