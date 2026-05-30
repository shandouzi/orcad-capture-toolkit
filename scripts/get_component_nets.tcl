if {![info exists targetRefDes]} {
    set targetRefDes ""
}
set logFile "./scripts/output_get_component_nets.txt"
set fp [open $logFile "w"]

proc log {msg} {
    upvar fp fp
    puts $fp $msg
    puts $msg
}

catch {

log "=========================================="
log "  GET COMPONENT PIN-NET EXPORT"
log "=========================================="
log ""

if {$targetRefDes == ""} {
    log "WARNING: targetRefDes is empty, exporting ALL components."
    log "  To filter, edit line 1 of this script: set targetRefDes \"J1\""
    log ""
}

log "Target RefDes: $targetRefDes"
log ""

set lDesign [GetActivePMDesign]
set lStatus [DboState]

if {$lDesign == "NULL" || $lDesign == ""} {
    log "ERROR: No active design. Open a DSN file first."
    close $fp
    return
}

set designNameCS [DboTclHelper_sMakeCString]
catch { $lDesign GetName $designNameCS }
set designName [DboTclHelper_sGetConstCharPtr $designNameCS]
set designName [file tail $designName]
set designName [file rootname $designName]
log "Design: $designName"

set rootRes [list]
catch { set rootRes [$lDesign GetRootSchematic $lStatus] }
set lRootSch [lindex $rootRes 0]

if {$lRootSch == "NULL" || $lRootSch == ""} {
    log "ERROR: GetRootSchematic failed."
    close $fp
    return
}

set allRows {}
set foundRefDesList {}
set totalPins 0
set foundTarget 0

proc processSchematic {lSch lStatus parentPath targetRefDes} {
    upvar allRows allRows
    upvar foundRefDesList foundRefDesList
    upvar totalPins totalPins
    upvar foundTarget foundTarget
    upvar fp fp

    set schCS [DboTclHelper_sMakeCString]
    catch { $lSch GetName $schCS }
    set schName [DboTclHelper_sGetConstCharPtr $schCS]

    set pageIterRes [list]
    catch { set pageIterRes [$lSch NewPagesIter $lStatus] }
    set lPageIter [lindex $pageIterRes 0]

    set pgIdx 0
    while {$pgIdx < 500} {
        set pgRes [list]
        catch { set pgRes [$lPageIter NextPage $lStatus] }
        set lPage [lindex $pgRes 0]
        if {$lPage == "" || $lPage == "NULL"} { break }

        set pgCS [DboTclHelper_sMakeCString]
        $lPage GetName $pgCS
        set pgName [DboTclHelper_sGetConstCharPtr $pgCS]

        set pagePath "$parentPath/$pgName"

        set piRes [list]
        catch { set piRes [$lPage NewPartInstsIter $lStatus] }
        set lPIter [lindex $piRes 0]

        set pc 0
        while {$pc < 2000} {
            set pRes [list]
            catch { set pRes [$lPIter NextPartInst $lStatus] }
            set lPI [lindex $pRes 0]
            if {$lPI == "" || $lPI == "NULL"} { break }

            set refCS [DboTclHelper_sMakeCString]
            catch { $lPI GetReferenceDesignator $refCS }
            set refdes [DboTclHelper_sGetConstCharPtr $refCS]

            set valCS [DboTclHelper_sMakeCString]
            catch { $lPI GetPartValue $valCS }
            set partValue [DboTclHelper_sGetConstCharPtr $valCS]

            set isHier 0
            set cntRes [list]
            catch { set cntRes [$lPI GetContents $lStatus] }
            set lView [lindex $cntRes 0]
            if {$lView != "" && $lView != "NULL"} {
                set isHier 1
            }

            if {$isHier} {
                set childSch [DboViewToDboSchematic $lView]
                if {$childSch != "" && $childSch != "NULL"} {
                    processSchematic $childSch $lStatus "$parentPath/$refdes" $targetRefDes
                }
            } else {
                if {$targetRefDes != "" && $refdes != $targetRefDes} {
                    incr pc
                    continue
                }

                lappend foundRefDesList $refdes

                set pinsRes [list]
                catch { set pinsRes [$lPI NewPinsIter $lStatus] }
                set pinsIter [lindex $pinsRes 0]

                if {$pinsIter == "" || $pinsIter == "NULL"} {
                    incr pc
                    continue
                }

                set pinIdx 0
                while {$pinIdx < 1000} {
                    set pinRes [list]
                    catch { set pinRes [$pinsIter NextPin $lStatus] }
                    set lPin [lindex $pinRes 0]
                    if {$lPin == "" || $lPin == "NULL"} { break }

                    set pnCS [DboTclHelper_sMakeCString]
                    catch { $lPin GetPinName $pnCS }
                    set pinName [DboTclHelper_sGetConstCharPtr $pnCS]

                    set pnumCS [DboTclHelper_sMakeCString]
                    catch { $lPin GetPinNumber $pnumCS }
                    set pinNumber [DboTclHelper_sGetConstCharPtr $pnumCS]

                    set netName ""
                    set netRes [list]
                    catch { set netRes [$lPin GetNet $lStatus] }
                    set lNet [lindex $netRes 0]
                    if {$lNet != "" && $lNet != "NULL"} {
                        set nnCS [DboTclHelper_sMakeCString]
                        catch { $lNet GetNetName $nnCS }
                        set netName [DboTclHelper_sGetConstCharPtr $nnCS]
                    }

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

                    lappend allRows [list $refdes $partValue $pinNumber $pinName $netName $pagePath]

                    incr pinIdx
                    incr totalPins
                }

                if {$refdes == $targetRefDes} {
                    set foundTarget 1
                }
            }

            incr pc
        }

        incr pgIdx
    }
}

log "Starting recursive hierarchy scan..."
log ""

processSchematic $lRootSch $lStatus "ROOT" $targetRefDes

if {$targetRefDes != "" && !$foundTarget} {
    log "WARNING: RefDes '$targetRefDes' not found in design!"
    log "Found RefDes list (first 50):"
    set uniqueRefs {}
    foreach r $foundRefDesList {
        if {[lsearch $uniqueRefs $r] == -1} {
            lappend uniqueRefs $r
        }
    }
    foreach r [lrange $uniqueRefs 0 49] {
        log "  $r"
    }
    log "  ... total unique RefDes: [llength $uniqueRefs]"
    log ""
}

if {[llength $allRows] > 0} {
    log "=========================================="
    log "  DATA SUMMARY"
    log "=========================================="
    log "  Total pins extracted: $totalPins"
    log "  Target RefDes: $targetRefDes"
    log "  Found: $foundTarget"
    log "=========================================="
    log ""

    log "=== Console Preview (first 20 rows) ==="
    log [format "%-10s %-20s %-8s %-10s %-30s %s" "RefDes" "PartValue" "PinNum" "PinName" "NetName" "Page"]
    log [string repeat "-" 120]

    set previewCount 0
    foreach row $allRows {
        if {$previewCount >= 20} { break }
        log [format "%-10s %-20s %-8s %-10s %-30s %s" \
            [lindex $row 0] [lindex $row 1] [lindex $row 2] [lindex $row 3] [lindex $row 4] [lindex $row 5]]
        incr previewCount
    }
    if {[llength $allRows] > 20} {
        log "... ([llength $allRows] total rows)"
    }
    log ""

    if {$targetRefDes != ""} {
        set csvFile "./${designName}_${targetRefDes}_pin_nets.csv"
    } else {
        set csvFile "./${designName}_pin_nets.csv"
    }
    set cfp [open $csvFile "w"]
    puts $cfp "RefDes,PartValue,PinNumber,PinName,NetName,PagePath"

    foreach row $allRows {
        set outRow {}
        foreach field $row {
            regsub -all {,} $field { } field
            lappend outRow $field
        }
        puts $cfp [join $outRow ","]
    }
    close $cfp
    log "CSV saved to: $csvFile"
    log "  Total rows: [llength $allRows]"
} else {
    log "No data extracted."
}

log ""
log "=========================================="
log "  DONE"
log "=========================================="

} bigErr

if {$bigErr != ""} {
    log "OUTER ERROR: $bigErr"
}
close $fp
# design by shandouzi
