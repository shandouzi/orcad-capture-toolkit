# OrCAD Capture CIS 17.2 TCL Dbo API 参考

本文档提炼自实际调试经验，覆盖 OrCAD Capture CIS 17.2 中常用的 Dbo TCL API 调用方式。

## 入口对象

### 获取当前工程（Design 模式）

```tcl
set lDesign [GetActivePMDesign]
```

返回 `DboDesign` 对象。必须在 DSN 工程打开状态下使用。

### 获取当前库（Library Editor 模式）

```tcl
set theLib [GetActivePMLastLibrary]
```

返回 `DboLib` 对象。必须在 Library Editor 窗口中使用。

**注意：** `GetActivePMDesign` 和 `GetActiveLib` 在 Library Editor 下均返回 NULL。

### 状态对象

```tcl
set lStatus [DboState]
```

几乎所有 Dbo API 调用都需要 `DboState` 作为参数。必须在使用其他 API 前创建。

---

## 字符串系统（三步模式）

Cadence Dbo API 的字符串获取遵循统一的三步模式：

```tcl
; 1. 创建 CString 容器
set cstr [DboTclHelper_sMakeCString]

; 2. API 将值填入 CString
$obj GetName $cstr

; 3. 转为 Tcl 字符串
set str [DboTclHelper_sGetConstCharPtr $cstr]
```

**适用范围：** `GetName`、`GetPinName`、`GetPinNumber`、`GetNetName`、`GetReferenceDesignator`、`GetPartValue`、`GetSchematicName` 等所有返回字符串的 API。

**注意：** 不能直接 `CString` 创建，也不能直接从 API 返回值中获取字符串。必须通过 `DboTclHelper_sMakeCString` 和 `DboTclHelper_sGetConstCharPtr`。

---

## SWIG 返回值处理（catch + lindex 模式）

Cadence SWIG 绑定中，许多方法返回多个值（包含 DboState 状态码），直接赋值会导致 `invalid command name "0"` 错误。

**必须使用 catch + lindex 模式：**

```tcl
; 错误 — 导致 invalid command name "0"
set lPart [$lPIter NextPartInst $lStatus]

; 正确 — catch + lindex 取第一个返回值
set res [list]
catch { set res [$lPIter NextPartInst $lStatus] }
set lPart [lindex $res 0]
```

**适用范围：** `GetRootSchematic`、`NextPage`、`NextPartInst`、`NextPin`、`NextDevice`、`GetContents`、`GetNet`、`GetWire`、`NewPagesIter`、`NewPartInstsIter`、`NewPinsIter`、`NewDevicesIter` 等几乎所有 SWIG 绑定方法。

**特殊情况：** 某些方法如 `GetPinName`、`GetPinNumber` 在 catch 后 CString 仍被正确填充（即使 catch 捕获到 DboState 对象）。

---

## 对象层次结构

### Design 模式

```
DboDesign
  └── DboSchematic (Root)
        └── DboPage
              ├── DboTitleBlock
              └── DboPartInst
                    ├── 普通器件 → 提取 Pin-Net
                    └── Hierarchy Block → DboView → DboSchematic (递归)
```

### Library 模式

```
DboLib
  └── DboLibPart
        ├── DboSymbolPin (Normal / Convert 视图)
        └── DboPackage
              └── DboDevice
                    └── SemanticString (包含 PinNumber 映射)
```

---

## Design 模式 API

### 获取 Root Schematic

```tcl
set rootRes [list]
catch { set rootRes [$lDesign GetRootSchematic $lStatus] }
set lRootSch [lindex $rootRes 0]
```

### 遍历 Page（本地顺序）

```tcl
set pageIterRes [list]
catch { set pageIterRes [$lSchematic NewPagesIter $lStatus] }
set lPageIter [lindex $pageIterRes 0]

while {$idx < 500} {
    set pgRes [list]
    catch { set pgRes [$lPageIter NextPage $lStatus] }
    set lPage [lindex $pgRes 0]
    if {$lPage == "" || $lPage == "NULL"} { break }
    ; 处理 lPage...
    incr idx
}
```

**注意：** `NewPagesIter` 返回顺序是数据库内部顺序，不是标题栏页号顺序。

### 遍历 Page（全局 TitleBlock 顺序）

```tcl
set pageList [DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign]
set lIter    [DboRefDesUtils_NewListIter $pageList]

set globalIdx 0
while {[$lIter hasNext]} {
    set item  [$lIter next]
    set lPage [DboPageStructOcc_getPage $item]
    incr globalIdx
    ; globalIdx 即为全局页码
}
```

**关键点：**
- 参数仅需 `$lDesign`，不需要 `$lStatus`
- 返回的迭代器使用 `hasNext`/`next` 模式（非 Capture 常见的 `Next` 模式）
- 自动处理层次化设计，子模块页面穿插在父页面对应位置

### 遍历 PartInst

```tcl
set piRes [list]
catch { set piRes [$lPage NewPartInstsIter $lStatus] }
set lPIter [lindex $piRes 0]

while {$pc < 2000} {
    set pRes [list]
    catch { set pRes [$lPIter NextPartInst $lStatus] }
    set lPI [lindex $pRes 0]
    if {$lPI == "" || $lPI == "NULL"} { break }
    ; 处理 lPI...
    incr pc
}
```

### 获取器件位号和值

```tcl
set refCS [DboTclHelper_sMakeCString]
catch { $lPI GetReferenceDesignator $refCS }
set refdes [DboTclHelper_sGetConstCharPtr $refCS]

set valCS [DboTclHelper_sMakeCString]
catch { $lPI GetPartValue $valCS }
set partValue [DboTclHelper_sGetConstCharPtr $valCS]
```

### 判断 Hierarchy Block

```tcl
set cntRes [list]
catch { set cntRes [$lPI GetContents $lStatus] }
set lView [lindex $cntRes 0]

if {$lView != "" && $lView != "NULL"} {
    ; 是 Hierarchy Block
    set childSch [DboViewToDboSchematic $lView]
    ; 递归处理 childSch
} else {
    ; 是普通器件
}
```

### 遍历 Pin

```tcl
set pinsRes [list]
catch { set pinsRes [$lPI NewPinsIter $lStatus] }
set pinsIter [lindex $pinsRes 0]

while {$pinIdx < 1000} {
    set pinRes [list]
    catch { set pinRes [$pinsIter NextPin $lStatus] }
    set lPin [lindex $pinRes 0]
    if {$lPin == "" || $lPin == "NULL"} { break }
    ; 处理 lPin...
    incr pinIdx
}
```

**注意：** 必须用 `NewPinsIter`，不是 `NewPinInstsIter`。后者在 Design 模式下返回 NULL。

### 获取 Pin 属性

```tcl
; 引脚功能名
set pnCS [DboTclHelper_sMakeCString]
catch { $lPin GetPinName $pnCS }
set pinName [DboTclHelper_sGetConstCharPtr $pnCS]

; 引脚编号
set pnumCS [DboTclHelper_sMakeCString]
catch { $lPin GetPinNumber $pnumCS }
set pinNumber [DboTclHelper_sGetConstCharPtr $pnumCS]

; 引脚类型（整数枚举）
catch { set pinTypeNum [$lPin GetPinType $lStatus] }
```

Pin 对象类型为 `DboPortInst`（非 `DboSymbolPin`，后者仅 Library 模式可用）。

### 获取 NetName（最关键）

**主路径：通过 DboNet**

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

**备用路径：通过 DboWire**

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

**关键：** 必须用 `GetNetName`，不能用 `GetName`。`GetName` 在 DboNet 上返回空字符串。

### TitleBlock 操作

```tcl
set lTBIter [$lPage NewTitleBlocksIter $lStatus]
set lTB [$lTBIter NextTitleBlock $lStatus]

if {$lTB != "NULL"} {
    ; 必须传 $lStatus，否则返回 0
    set pageNum [$lTB GetPageNumber $lStatus]
    set pageCnt [$lTB GetPageCount $lStatus]

    ; 模块名
    set schCStr [DboTclHelper_sMakeCString]
    catch { $lTB GetSchematicName $schCStr }
    set moduleName [DboTclHelper_sGetConstCharPtr $schCStr]

    ; 属性读取
    set propNameCStr [DboTclHelper_sMakeCString]
    set valCStr [DboTclHelper_sMakeCString]
    DboTclHelper_sSetCString $propNameCStr "Page Count"
    $lTB GetEffectivePropStringValue $propNameCStr $valCStr
    ; 注意："Page Count" 返回全局总页数，非本地页数
}
```

### EffectiveProp 属性名

| 属性名 | 返回值 | 说明 |
|---|---|---|
| `Page Number` | 本地页码 | 同 `GetPageNumber` |
| `Page Count` | 全局总页数 | 非 `GetPageCount` 的本地值 |
| `PageNumber` | 空 | 大小写敏感 |
| `page_number` | 空 | 大小写敏感 |

---

## Library 模式 API

### 遍历 Part

```tcl
set lPartIter [DboLib_NewPartsIter $theLib $lStatus]
while {1} {
    set partRes [list]
    catch { set partRes [$lPartIter NextPart $lStatus] }
    set lPart [lindex $partRes 0]
    if {$lPart == "" || $lPart == "NULL"} { break }
}
```

### 获取 Part 属性

```tcl
$lPart GetReference $cstr            ; 参考位号前缀 (U, R, C...)
$lPart GetPartValue $cstr            ; Part Value
$lPart GetName $cstr                 ; 完整名 (GTL2003PW.Normal)
$lPart GetContentsViewType $lStatus  ; 视图类型 (0=Normal, 1=Convert)
$lPart GetPackagePtr                 ; 获取 Package 对象
```

### 遍历 Library Pin

```tcl
set lPinIter [$lPart NewLPinsIter $lStatus]
while {1} {
    set pinRes [list]
    catch { set pinRes [$lPinIter NextPin $lStatus] }
    set lPin [lindex $pinRes 0]
    if {$lPin == "" || $lPin == "NULL"} { break }
}
```

### Library Pin 属性

```tcl
$lPin GetPinName $cstr          ; 引脚名称
$lPin GetPinType $lStatus       ; 引脚类型（整数枚举）
$lPin GetSemanticString $cstr   ; 完整语义字符串
```

### 获取 PinNumber（通过 Package → Device）

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
    ; 从 devSS 中正则提取 PinNumber(index) = value
}
```

### SemanticString 解析

`GetSemanticString` 返回的文本包含完整属性，可正则提取：

```tcl
; Pin 属性
regexp {PinType = (\w+)} $semStr match pinType
regexp {PinPosition = (\d+)} $semStr match pinPosition

; Device 中的引脚编号映射
regexp {PinNumber\((\d+)\) = (\w+)} $devSS match idx val
```

---

## 枚举值映射

### PinType

| 枚举值 | 含义 |
|---|---|
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

## 不可用的 API（OrCAD 17.2）

以下写入操作在 OrCAD 17.2 中均静默失败：

| API | 行为 |
|---|---|
| `DboNet_SetName` | 静默失败 |
| `DboSchematicNet_SetName` | 静默失败 |
| `DboWireScalar_SetName` | 静默失败 |
| `DboAlias_SetName` | Alias 对象不可获取 |
| `SetEffectivePropStringValue("Name", ...)` | 无效 |

以下路径返回 NULL（不支持 Occurrence）：

| API | 返回 |
|---|---|
| `$lDesign GetFlatSchematic $lStatus` | NULL |
| `$lDesign GetRootSchematicOccurrence $lStatus` | NULL |
| `$childSch GetOccurrence $lStatus` | NULL |

Page 上的 Net 迭代器全部返回 NULL，Net 必须通过 Pin → GetNet 获取：

| API | 返回 |
|---|---|
| `$page NewNetsIter $lStatus` | NULL |
| `$page NewNetInstsIter $lStatus` | NULL |
| `$page NewSignalNetsIter $lStatus` | NULL |
