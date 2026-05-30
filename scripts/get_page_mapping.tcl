set logFile "./scripts/output_get_page_mapping.txt"
set fp [open $logFile "w"]

proc log {msg} {
    upvar fp fp
    puts $fp $msg
    puts $msg
}

catch {

log "=========================================="
log "  PAGE NUMBER -> PAGE NAME MAPPING (Global)"
log "=========================================="

set lDesign [GetActivePMDesign]
set lStatus [DboState]

log ""
log "=== Step 1: Get all pages in TitleBlock order ==="
set pageList [DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder $lDesign]
set lIter [DboRefDesUtils_NewListIter $pageList]

set globalIdx 0
set gRows {}

while {[$lIter hasNext]} {
    set item [$lIter next]
    incr globalIdx

    set lPage [DboPageStructOcc_getPage $item]
    if {$lPage == "NULL"} {
        log "  [$globalIdx]: NULL page"
        continue
    }

    set pageCStr [DboTclHelper_sMakeCString]
    $lPage GetName $pageCStr
    set rawName [DboTclHelper_sGetConstCharPtr $pageCStr]

    set cleanName $rawName
    regsub {^[A-Za-z](\d)} $cleanName {\1} cleanName

    set pageNum -1
    set pageCnt -1
    set moduleName ""

    set lTBIter [$lPage NewTitleBlocksIter $lStatus]
    set lTB     [$lTBIter NextTitleBlock $lStatus]

    if {$lTB != "NULL"} {
        catch { set pageNum [$lTB GetPageNumber $lStatus] }
        catch { set pageCnt [$lTB GetPageCount $lStatus] }

        set schCStr [DboTclHelper_sMakeCString]
        catch { $lTB GetSchematicName $schCStr }
        set moduleName [DboTclHelper_sGetConstCharPtr $schCStr]
    }

    lappend gRows [list $globalIdx $pageNum $pageCnt $cleanName $moduleName]

    log [format "%4d  |  LocalPage %2d of %-2d | %-35s | %s" \
        $globalIdx $pageNum $pageCnt $cleanName $moduleName]
}

log ""
log "=========================================="
log "  SUMMARY (Global Page Number -> PageName)"
log "=========================================="

foreach row $gRows {
    set gNum     [lindex $row 0]
    set localNum [lindex $row 1]
    set localCnt [lindex $row 2]
    set pageName [lindex $row 3]
    set module   [lindex $row 4]
    log [format "  %3d -> %-35s (%s, local %d of %d)" \
        $gNum $pageName $module $localNum $localCnt]
}

log ""
log "Total global pages: $globalIdx"
log "=========================================="

log ""
log "=== Writing CSV ==="
set csvFile "./page_mapping.csv"
set cfp [open $csvFile "w"]
puts $cfp "GlobalPage,LocalPage,LocalTotal,PageName,Module"

foreach row $gRows {
    set gNum     [lindex $row 0]
    set localNum [lindex $row 1]
    set localCnt [lindex $row 2]
    set pageName [lindex $row 3]
    set module   [lindex $row 4]
    puts $cfp "$gNum,$localNum,$localCnt,$pageName,$module"
}

close $cfp
log "CSV saved to: $csvFile"

} bigErr

if {$bigErr != ""} {
    log "ERROR: $bigErr"
}

close $fp
# design by shandouzi