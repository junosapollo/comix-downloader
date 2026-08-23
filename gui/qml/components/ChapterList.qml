import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    
    ListModel { id: chapterModel }
    property var allChapters: []  // Store original list for filtering
    property string currentFilter: "Any"
    // Selection is keyed by the stable chapter id rather than stored on two
    // independently copied model objects. This keeps the counter and the
    // visible delegates in sync with the chapters sent to the download bridge.
    property var selectedChapterIds: ({})
    property int selectedCount: 0
    
    // Theme colors
    readonly property color bgCard: "#1C1C24"
    readonly property color bgElevated: "#252530"
    readonly property color accentPrimary: "#E8A54B"
    readonly property color textPrimary: "#F5F5F0"
    readonly property color textSecondary: "#8B8B99"
    readonly property color textTertiary: "#5C5C66"
    
    color: bgCard
    radius: 12
    
    function setChapters(chapterList) {
        allChapters = chapterList || []
        selectedChapterIds = ({})
        selectedCount = 0
        applyFilter(currentFilter)
    }

    function chapterKey(chapterId) {
        return String(chapterId)
    }

    function isChapterSelected(chapterId) {
        return !!selectedChapterIds[chapterKey(chapterId)]
    }

    function copySelection(nextSelection) {
        var copy = {}
        var keys = Object.keys(nextSelection)
        for (var i = 0; i < keys.length; i++) {
            copy[keys[i]] = true
        }
        return copy
    }

    function updateSelectionCount() {
        selectedCount = Object.keys(selectedChapterIds).length
    }

    function setChapterSelected(chapterId, selected) {
        var key = chapterKey(chapterId)
        var nextSelection = copySelection(selectedChapterIds)
        if (selected) {
            nextSelection[key] = true
        } else {
            delete nextSelection[key]
        }

        selectedChapterIds = nextSelection
        updateSelectionCount()

        // Keep the currently visible model synchronized immediately. The
        // filtered model is rebuilt from selectedChapterIds when the filter
        // changes, so hidden rows are never modified by this operation.
        for (var i = 0; i < chapterModel.count; i++) {
            if (chapterKey(chapterModel.get(i).chapter_id) === key) {
                chapterModel.setProperty(i, "selected", selected)
                break
            }
        }
    }

    function setVisibleSelection(selected) {
        var nextSelection = copySelection(selectedChapterIds)
        for (var i = 0; i < chapterModel.count; i++) {
            var key = chapterKey(chapterModel.get(i).chapter_id)
            if (selected) {
                nextSelection[key] = true
            } else {
                delete nextSelection[key]
            }
            chapterModel.setProperty(i, "selected", selected)
        }

        selectedChapterIds = nextSelection
        updateSelectionCount()
    }
    
    function applyFilter(filter) {
        currentFilter = filter
        chapterModel.clear()
        
        for (var i = 0; i < allChapters.length; i++) {
            var ch = allChapters[i]
            if (filter === "Any" || !filter || ch.group_name === filter) {
                chapterModel.append({
                    "chapter_id": ch.chapter_id,
                    "number": ch.number,
                    "title": ch.title !== undefined ? ch.title : "",
                    "volume": ch.volume !== undefined ? ch.volume : "",
                    "votes": ch.votes !== undefined ? ch.votes : 0,
                    "group_name": ch.group_name !== undefined ? ch.group_name : "",
                    "pages_count": ch.pages_count !== undefined ? ch.pages_count : 0,
                    "selected": isChapterSelected(ch.chapter_id)
                })
            }
        }
    }
    
    function getSelectedChapters() {
        var selected = []
        for (var i = 0; i < allChapters.length; i++) {
            var chapter = allChapters[i]
            if (!isChapterSelected(chapter.chapter_id)) continue

            // Return a fresh object so callers cannot mutate the canonical
            // chapter records or the selection state accidentally.
            var selectedChapter = {}
            for (var key in chapter) {
                selectedChapter[key] = chapter[key]
            }
            selectedChapter.selected = true
            selected.push(selectedChapter)
        }
        return selected
    }
    
    function getScanlators() {
        var scanlators = new Set()
        for (var i = 0; i < allChapters.length; i++) {
            if (allChapters[i].group_name) {
                scanlators.add(allChapters[i].group_name)
            }
        }
        var result = ["Any"]
        scanlators.forEach(function(s) { result.push(s) })
        return result
    }
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8
        
        // HEADER
        RowLayout {
            Layout.fillWidth: true
            
            Text {
                text: "CHAPTERS"
                font.family: "Segoe UI"
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: textPrimary
                
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: -2
                    width: parent.width
                    height: 2
                    color: accentPrimary
                    opacity: 0.5
                    radius: 1
                }
            }
            
            Item { Layout.fillWidth: true }
            
            // Show filtered / total count
            Text {
                text: {
                    if (currentFilter !== "Any") {
                        return chapterModel.count + " shown (of " + allChapters.length + ")"
                    }
                    return allChapters.length + " available"
                }
                font.pixelSize: 12
                color: currentFilter !== "Any" ? accentPrimary : textTertiary
            }
        }
        
        // CHAPTER LIST
        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: chapterModel
            clip: true
            spacing: 4
            
            ScrollBar.vertical: ScrollBar { 
                policy: ScrollBar.AsNeeded
                
                background: Rectangle {
                    implicitWidth: 8
                    color: bgElevated
                    radius: 4
                }
                
                contentItem: Rectangle {
                    implicitWidth: 8
                    radius: 4
                    color: parent.pressed ? accentPrimary : (parent.hovered ? Qt.lighter(accentPrimary, 1.3) : textTertiary)
                    
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
            }
            
            delegate: ChapterDelegate {
                id: chapterDelegate
                width: listView.width - 10
                chapter: ({
                    "chapter_id": model.chapter_id,
                    "number": model.number,
                    "title": model.title,
                    "group_name": model.group_name,
                    "selected": model.selected
                })
                onToggled: {
                    root.setChapterSelected(model.chapter_id, !root.isChapterSelected(model.chapter_id))
                }
                
                // Reference the parent ChapterList
                property var chapterList: root
            }
            
            Text {
                anchors.centerIn: parent
                text: currentFilter !== "Any" ? "No chapters from this scanlator" : "Enter a manga URL to see chapters"
                font.pixelSize: 14
                color: textTertiary
                visible: chapterModel.count === 0
            }
        }
        
        // SELECTION CONTROLS
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            
            Rectangle {
                implicitWidth: allText.width + 16
                implicitHeight: 28
                color: allArea.containsMouse ? bgElevated : "transparent"
                border.color: textTertiary; border.width: 1; radius: 6
                Text { id: allText; anchors.centerIn: parent; text: "Select All"; font.pixelSize: 12; color: textSecondary }
                MouseArea { id: allArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.setVisibleSelection(true)
                    }
                }
            }
            
            Rectangle {
                implicitWidth: noneText.width + 16
                implicitHeight: 28
                color: noneArea.containsMouse ? bgElevated : "transparent"
                border.color: textTertiary; border.width: 1; radius: 6
                Text { id: noneText; anchors.centerIn: parent; text: "None"; font.pixelSize: 12; color: textSecondary }
                MouseArea { id: noneArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.setVisibleSelection(false)
                    }
                }
            }
            
            Item { Layout.fillWidth: true }
            
            Text {
                text: selectedCount + " selected"
                font.pixelSize: 12
                color: accentPrimary
            }
        }
    }
}
