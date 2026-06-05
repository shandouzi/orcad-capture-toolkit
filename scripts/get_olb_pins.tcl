proc log {msg} {
    upvar fp fp
    puts $fp $msg
    puts $msg
}

set fp stdout

catch {

set lStatus [DboState]

set theLib [GetActivePMLastLibrary]
set libNameCS [DboTclHelper_sMakeCString]
DboLib_GetName $theLib $libNameCS
set libName [DboTclHelper_sGetConstCharPtr $libNameCS]
set libShortName [file tail [file rootname $libName]]

set logFile "./scripts/${libShortName}_output.txt"
set fp [open $logFile "w"]

log "=========================================="
log "  OLB PIN INFO EXPORT"
log "=========================================="
log ""
log "Lib: $libName"
log ""

set pinTypeMap(0) "Open"
set pinTypeMap(1) "Bidirectional"
set pinTypeMap(2) "Output3State"
set pinTypeMap(3) "Output"
set pinTypeMap(4) "Input"
set pinTypeMap(5) "OpenCollector"
set pinTypeMap(6) "Passive"
set pinTypeMap(7) "Power"
set pinTypeMap(8) "Passive"
set pinTypeMap(9) "HIZ"
set pinTypeMap(10) "Short"
set pinTypeMap(11) "Shorted"

set lPartIter [DboLib_NewPartsIter $theLib $lStatus]
set allRows {}
set partCount 0
set totalPinCount 0
set partIdx 0

set lastPkgName ""

while {$partIdx < 5000} {
    set partRes [list]
    catch { set partRes [$lPartIter NextPart $lStatus] }
    set lPart [lindex $partRes 0]
    if {$lPart == "" || $lPart == "NULL"} { break }

    set pRefCS [DboTclHelper_sMakeCString]
    $lPart GetReference $pRefCS
    set partRef [DboTclHelper_sGetConstCharPtr $pRefCS]

    set pNameCS [DboTclHelper_sMakeCString]
    $lPart GetName $pNameCS
    set partFullName [DboTclHelper_sGetConstCharPtr $pNameCS]

    set pValCS [DboTclHelper_sMakeCString]
    $lPart GetPartValue $pValCS
    set partValue [DboTclHelper_sGetConstCharPtr $pValCS]

    set viewType ""
    catch { set viewType [$lPart GetContentsViewType $lStatus] }
    if {$viewType == 0} { set viewType "Normal" } elseif {$viewType == 1} { set viewType "Convert" } else { set viewType "Unknown$viewType" }

    set pkg ""
    set pkgRes [list]
    catch { set pkgRes [$lPart GetPackagePtr] }
    set pkg [lindex $pkgRes 0]
    set pkgName ""
    if {$pkg != "" && $pkg != "NULL"} {
        set pkgCS [DboTclHelper_sMakeCString]
        $pkg GetName $pkgCS
        set pkgName [DboTclHelper_sGetConstCharPtr $pkgCS]
    }

    if {$pkgName != $lastPkgName} {
        set lastPkgName $pkgName
        array unset pkgDevSS
        array unset pkgDevCell
        set pkgDevTotal 0
        if {$pkg != "" && $pkg != "NULL"} {
            set devIterRes [list]
            catch { set devIterRes [$pkg NewDevicesIter $lStatus] }
            set devIter [lindex $devIterRes 0]
            if {$devIter != "" && $devIter != "NULL"} {
                set di 1
                while {1} {
                    set devRes [list]
                    catch { set devRes [$devIter NextDevice $lStatus] }
                    set dev [lindex $devRes 0]
                    if {$dev == "" || $dev == "NULL"} { break }
                    set devSSCS [DboTclHelper_sMakeCString]
                    catch { $dev GetSemanticString $devSSCS }
                    set pkgDevSS($di) [DboTclHelper_sGetConstCharPtr $devSSCS]
                    set cName ""
                    regexp {Cell = ([^\r\n]+)} $pkgDevSS($di) -> cName
                    set pkgDevCell($di) $cName
                    log "  Cached Device $di Cell='$cName'"
                    incr di
                }
                set pkgDevTotal [expr {$di - 1}]
            }
        }
    }

    set nameNoView [lindex [split $partFullName "."] 0]
    set deviceNum -1
    for {set di 1} {$di <= $pkgDevTotal} {incr di} {
        if {[info exists pkgDevCell($di)] && $pkgDevCell($di) eq $nameNoView} {
            set deviceNum $di
            break
        }
    }

    if {$deviceNum == -1} {
        log "  WARNING: No Cell match for '$nameNoView'"
        set deviceNum 0
    }

    log "----------------------------------------"
    log "Part: $partValue  Ref: $partRef  View: $viewType  Section: $deviceNum"
    log "  FullName: $partFullName"
    log "  Package: $pkgName  Matched Device: $deviceNum"
    log "----------------------------------------"

    if {$partValue == ""} {
        set partValue $pkgName
    }

    incr partCount

    set devSS ""
    if {$deviceNum > 0 && [info exists pkgDevSS($deviceNum)]} {
        set devSS $pkgDevSS($deviceNum)
    }

    array unset pinNumMap
    if {$devSS != ""} {
        set matchPos 0
        while {[regexp -start $matchPos -indices {PinNumber\((\d+)\) = (\w+)} $devSS match sub0 sub1]} {
            set idxStart [lindex $sub0 0]
            set idxEnd [lindex $sub0 1]
            set idxVal [string range $devSS $idxStart $idxEnd]
            set valStart [lindex $sub1 0]
            set valEnd [lindex $sub1 1]
            set pinVal [string range $devSS $valStart $valEnd]
            set pinNumMap($idxVal) $pinVal
            set matchPos [expr {[lindex $match 1] + 1}]
        }
    }

    set lPinIter [$lPart NewLPinsIter $lStatus]
    set pinIdx 0
    while {$pinIdx < 5000} {
        set pinRes [list]
        catch { set pinRes [$lPinIter NextPin $lStatus] }
        set lPin [lindex $pinRes 0]
        if {$lPin == "" || $lPin == "NULL"} { break }

        set pinNameCS [DboTclHelper_sMakeCString]
        $lPin GetPinName $pinNameCS
        set pinName [DboTclHelper_sGetConstCharPtr $pinNameCS]

        set pinTypeNum ""
        catch { set pinTypeNum [$lPin GetPinType $lStatus] }
        set pinTypeStr ""
        if {[info exists pinTypeMap($pinTypeNum)]} {
            set pinTypeStr $pinTypeMap($pinTypeNum)
        } else {
            set pinTypeStr "Type$pinTypeNum"
        }

        set semCS [DboTclHelper_sMakeCString]
        catch { $lPin GetSemanticString $semCS }
        set semStr [DboTclHelper_sGetConstCharPtr $semCS]

        set semPinType "UNKNOWN"
        if {[regexp {PinType = (\w+)} $semStr match spt]} {
            set semPinType $spt
        }

        set semPinPos "UNKNOWN"
        if {[regexp {PinPosition = (\d+)} $semStr match spp]} {
            set semPinPos $spp
        }

        set pinNum ""
        if {[info exists pinNumMap($pinIdx)]} {
            set pinNum $pinNumMap($pinIdx)
        }

        log [format "  Pin%02d: Name=%-25s  Number=%-8s  Position=%-4s  Type(Enum)=%-15s Type(Sem)=%s" \
            $pinIdx $pinName $pinNum $semPinPos $pinTypeStr $semPinType]

        set sortKey "${pkgName}|[format {%05d} $deviceNum]|[format {%05d} $pinIdx]"
        lappend allRows [list $sortKey $partValue $partRef $deviceNum $viewType $pinIdx $pinName $pinNum $semPinPos $pinTypeStr $semPinType $pkgName]

        incr pinIdx
        incr totalPinCount
    }
    log "  Pins: $pinIdx"
    log ""

    incr partIdx
}

log "=========================================="
log "  SUMMARY"
log "=========================================="
log "  Total Parts (Sections): $partCount"
log "  Total Pins: $totalPinCount"
log "=========================================="

set allRows [lsort -index 0 $allRows]

log ""
log "=== Writing CSV 1 (data only, sorted by Section) ==="
set csvFile "./${libShortName}_pin_info.csv"
set cfp [open $csvFile "w"]
puts $cfp "PartName,PartRef,Section,View,PinIndex,PinName,PinNumber,PinPosition,PinType(Enum),PinType(Semantic),Package"

foreach row $allRows {
    set data [lrange $row 1 end]
    puts $cfp [join $data ","]
}
close $cfp
log "CSV saved to: $csvFile"

log ""
log "=== Writing CSV 2 (with section headers & summary, sorted by Section) ==="
set csvFile2 "./${libShortName}_pin_info_detail.csv"
set cfp2 [open $csvFile2 "w"]

puts $cfp2 "Lib: $libName"
puts $cfp2 ""
puts $cfp2 "PartName,PartRef,Section,View,PinIndex,PinName,PinNumber,PinPosition,PinType(Enum),PinType(Semantic),Package"

set lastPartKey ""
foreach row $allRows {
    set data [lrange $row 1 end]
    set pKey "[lindex $data 0]|[lindex $data 1]|[lindex $data 2]|[lindex $data 3]|[lindex $data 10]"
    if {$pKey != $lastPartKey} {
        puts $cfp2 ""
        puts $cfp2 "# Part: [lindex $data 0]  Ref: [lindex $data 1]  Section: [lindex $data 2]  View: [lindex $data 3]  Package: [lindex $data 10]"
        set lastPartKey $pKey
    }
    puts $cfp2 [join $data ","]
}

puts $cfp2 ""
puts $cfp2 "# SUMMARY"
puts $cfp2 "Total Parts (Sections),$partCount"
puts $cfp2 "Total Pins,$totalPinCount"
puts $cfp2 "Lib,$libName"

close $cfp2
log "CSV saved to: $csvFile2"

} bigErr

if {$bigErr != ""} {
    if {$fp != "stdout"} {
        log "OUTER ERROR: $bigErr"
    }
    puts "OUTER ERROR: $bigErr"
}

if {$fp != "stdout"} {
    close $fp
}
