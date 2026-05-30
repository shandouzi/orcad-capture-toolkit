# Cadence OrCAD TCL 开发踩坑汇总

本文档汇总在实际开发 OrCAD Capture CIS 17.2 TCL 脚本过程中遇到的所有陷阱和解决方案。

---

## 坑 1：迭代器返回值导致 `invalid command name "0"`

**现象：**

```tcl
set lPart [$lPIter NextPartInst $lStatus]
; => invalid command name "0"
```

**根因：** Cadence SWIG 绑定中，方法的 Tcl 返回值包含多个值，其中状态码 `0` 被 Tcl 误解析为命令名。

**解决：**

```tcl
set res [list]
catch { set res [$lPIter NextPartInst $lStatus] }
set lPart [lindex $res 0]
```

**适用范围：** `NextPage`、`NextPartInst`、`NextPin`、`NextDevice`、`NextPart`、`GetRootSchematic`、`GetContents`、`GetNet`、`GetWire`、`NewPagesIter`、`NewPartInstsIter`、`NewPinsIter`、`NewDevicesIter` 等几乎所有 SWIG 方法。

---

## 坑 2：`GetName` vs `GetNetName`

**现象：** 在 DboNet 上调用 `GetName` 返回空字符串。

```tcl
$lNet GetName $cstr
DboTclHelper_sGetConstCharPtr $cstr  ; => '' (空)
```

**解决：** 必须用 `GetNetName`。

```tcl
$lNet GetNetName $cstr
DboTclHelper_sGetConstCharPtr $cstr  ; => 'GND' (正确)
```

**适用范围：** `DboNet` 和 `DboWire` 上都适用。

---

## 坑 3：catch 后 CString 仍有值

**现象：** `GetPinName` 被 catch 捕获，看似报错，但 CString 已被正确填充。

```tcl
set cstr [DboTclHelper_sMakeCString]
catch { $lPin GetPinName $cstr }
; catch 返回非 0（捕获到 DboState 对象）

DboTclHelper_sGetConstCharPtr $cstr  ; => 'VBAT' (有值！)
```

**根因：** SWIG 绑定中 `GetPinName` 返回多个值（DboState + void），Tcl 将 DboState 对象作为返回值抛出，被 catch 捕获。但 CString 引用参数已被 C++ 层正确写入。

**结论：** 不必担心 catch 的返回值，只要检查 CString 内容即可。

---

## 坑 4：`GetPageNumber` / `GetPageCount` 必须传 `$lStatus`

**现象：** 调用 `GetPageNumber` 始终返回 `0`。

**根因：** 漏传 `$lStatus` 参数。SWIG 绑定不会报错，但返回错误值。

```tcl
; 错误
$lTB GetPageNumber    ; => 0

; 正确
$lTB GetPageNumber $lStatus  ; => 真实页码
```

**影响：** `GetPageNumber`、`GetPageCount`、`GetPinType` 等方法均需传入 `$lStatus`。

---

## 坑 5：层次化设计中页码是模块内本地编号

**现象：** `GetPageNumber` 返回的页码在子模块中重新从 1 开始。

```
MAIN:       PageNumber 1-7,   PageCount 7
子模块 B:   PageNumber 1-7,   PageCount 7
子模块 P:   PageNumber 1-17,  PageCount 17
```

**解决：** 使用 `DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder` 获取全局排序的页面列表，位置索引即为全局页码。

```tcl
set pageList [DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign]
set lIter    [DboRefDesUtils_NewListIter $pageList]
```

**关键：** 参数仅需 `$lDesign`，不需要 `$lStatus`。

---

## 坑 6：全局列表迭代器使用 `hasNext`/`next` 模式

**现象：** 尝试使用 Capture 常见的 `NextXxx $lStatus` + NULL 判断模式遍历全局列表失败。

**解决：** `DboRefDesUtils_NewListIter` 返回的迭代器使用 Java 风格的 `hasNext`/`next` 模式：

```tcl
; 错误
$lIter NextPageStructOcc $lStatus

; 正确
while {[$lIter hasNext]} {
    set item  [$lIter next]
    set lPage [DboPageStructOcc_getPage $item]
}
```

---

## 坑 7：`NewPinsIter` vs `NewPinInstsIter`

**现象：** `NewPinInstsIter` 在 Design 模式下返回 NULL。

**解决：** Design 模式下使用 `NewPinsIter`：

```tcl
; 错误（Design 模式下返回 NULL）
$partInst NewPinInstsIter $lStatus

; 正确
$partInst NewPinsIter $lStatus
```

**原因：** Pin 对象类型不同：
- Design 模式：`DboPortInst`，用 `NewPinsIter`
- Library 模式：`DboSymbolPin`，用 `NewLPinsIter`

---

## 坑 8：Library Editor 下 `GetActivePMDesign` 返回 NULL

**现象：** 在 Library Editor 窗口中，所有 Design 级 API 返回 NULL。

```tcl
set lDesign [GetActivePMDesign]  ; => NULL
set lLib [GetActiveLib]           ; => NULL
set lSession [GetSession]         ; => NULL
```

**解决：** Library Editor 中使用 `GetActivePMLastLibrary`：

```tcl
set theLib [GetActivePMLastLibrary]  ; => _p_DboLib (成功)
```

---

## 坑 9：`DboSymbolPin` 上没有 `GetPinNumber` 方法

**现象：** Library 模式下 Pin 对象无法直接获取引脚编号。

**根因：** PinNumber 属于 Package → Device 层面，不在 Symbol Pin 上。

**解决：** 通过 Package → Device → SemanticString 间接获取：

```tcl
set pkg [$lPart GetPackagePtr]
set devIter [$pkg NewDevicesIter $lStatus]
set dev [$devIter NextDevice $lStatus]
$dev GetSemanticString $cstr
; 从返回文本中正则提取 PinNumber(index) = value
```

**注意：** 多 Section 器件必须遍历所有 Device 并合并 PinNumber 映射。

---

## 坑 10：CSV 编码不是 UTF-8

**现象：** 读取 OrCAD 导出的 CSV 时出现 `UnicodeDecodeError`。

**根因：** OrCAD Capture 导出的 CSV 可能使用 gb2312 编码。

**解决：** 多编码尝试：

```python
encodings = ["utf-8-sig", "utf-8", "gb2312", "gbk", "latin-1"]
for enc in encodings:
    try:
        with open(csv_path, "r", encoding=enc) as f:
            reader = csv.DictReader(f)
            # 处理数据
        break
    except (UnicodeDecodeError, UnicodeError):
        continue
```

---

## 坑 11：OrCAD 17.2 不支持 NetName 写入

**现象：** 所有 Dbo 级别的 Set 操作均静默失败（无报错，但值不变）。

已确认无效的 API：

| API | 行为 |
|---|---|
| `DboNet_SetName` | 静默失败 |
| `DboSchematicNet_SetName` | 静默失败 |
| `DboWireScalar_SetName` | 静默失败 |
| `DboAlias_SetName` | Alias 对象不可获取 |
| `PlaceNetAlias` | 仅交互模式，脚本不可用 |

**结论：** OrCAD 17.2 的 TCL API 仅支持读取，不支持网络名写入。SPB 23.1+ 版本可能支持。如需修改网络名，建议使用 OrCAD Find & Replace 功能或直接编辑 DSN 文件（后者有损坏风险）。

---

## 坑 12：Occurrence 路径全部 NULL

**现象：** 以下 API 均返回 NULL：

```tcl
$lDesign GetFlatSchematic $lStatus           ; => NULL
$lDesign GetRootSchematicOccurrence $lStatus ; => NULL
$childSch GetOccurrence $lStatus             ; => NULL
```

**结论：** 部分工程不支持 Occurrence 路径。所有操作必须通过 Schematic → Page → PartInst 路径进行。

---

## 坑 13：Page 上没有 Net 迭代器

**现象：** Page 上的所有 Net 迭代器返回 NULL：

```tcl
$page NewNetsIter $lStatus         ; => NULL
$page NewNetInstsIter $lStatus     ; => NULL
$page NewSignalNetsIter $lStatus   ; => NULL
```

**解决：** 通过 Pin → GetNet 获取 Net 对象。Page 上只有 `NewWiresIter` 有效。

---

## 坑 14：`targetRefDes` 变量被脚本内部覆盖

**现象：** 用户在 Command Window 中设置 `set targetRefDes "J1"`，执行脚本后被覆盖为空。

**解决：** 使用 `info exists` 检测：

```tcl
if {![info exists targetRefDes]} {
    set targetRefDes ""
}
```

---

## 坑 15：字段中的逗号破坏 CSV 格式

**现象：** PinName 中包含逗号（如 `PC13/TAMPER,RTC`）导致 CSV 列错位。

**解决：** 写入 CSV 前替换逗号：

```tcl
regsub -all {,} $field { } field
```

---

## 坑 16：字典序导致差分对分散

**现象：** 默认排序 `_N_0, _N_1, _N_10, _N_11, _N_2` 而非自然顺序。

**解决：** 提取末尾数字并补零：

```javascript
function netSortKey(net) {
    const m = net.match(/^(.*[._])(P|N)_(\d+)$/i);
    if (!m) return net;
    return m[1] + m[2].toUpperCase() + "_" + parseInt(m[3]).toString().padStart(3, '0');
}
```

---

## 坑 17：`DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder` 参数

**现象：** 传错参数导致报错。

```tcl
; 错误
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lRoot $lStatus   ; 报错
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign $lStatus ; 报错
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lRoot            ; 报错

; 正确 — 仅需 $lDesign 一个参数
DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign          ; 成功
```
