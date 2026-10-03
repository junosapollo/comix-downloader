import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    
    property string currentChapter: ""
    property int completedChapters: 0
    property int totalChapters: 0
    property bool isFinished: false
    property int successCount: 0
    property int failCount: 0
    property int cancelledCount: 0
    
    // Optional bridge context
    property var bridge: null
    
    // UI state
    property string viewFilter: "all"  // "all" | "failed"
    
    // O(1) maps: chapter name -> row index
    property var rowIndex: ({})
    property var failedIndex: ({})
    
    // Theme colors
    readonly property color bgCard: "#1C1C24"
    readonly property color bgElevated: "#252530"
    readonly property color accentPrimary: "#E8A54B"
    readonly property color accentHighlight: "#FFD93D"
    readonly property color textPrimary: "#F5F5F0"
    readonly property color textSecondary: "#8B8B99"
    readonly property color successColor: "#7CB342"
    readonly property color errorColor: "#E57373"
    
    color: bgCard
    radius: 12
    
    ListModel { id: taskModel }
    ListModel { id: failedModel }
    
    function reset() {
        currentChapter = ""; completedChapters = 0; totalChapters = 0
        isFinished = false; successCount = 0; failCount = 0; cancelledCount = 0
        viewFilter = "all"
        taskModel.clear()
        failedModel.clear()
        rowIndex = ({})
        failedIndex = ({})
    }
    
    function updateProgress(completed, total) {
        completedChapters = completed; totalChapters = total
    }
    
    function setChapterStatus(name, s, message) {
        currentChapter = name
        var isCancelled = (message === "Download cancelled")
        if (s) {
            successCount++
        } else if (isCancelled) {
            cancelledCount++
        }
        
        var i = rowIndex[name]
        if (i !== undefined && i < taskModel.count) {
            taskModel.setProperty(i, "status", s ? "Complete" : (isCancelled ? "Cancelled" : "Failed"))
            taskModel.setProperty(i, "progress", 100)
            if (!s && message && message.length > 0)
                taskModel.setProperty(i, "details", message)
        } else {
            taskModel.append({
                "name": name,
                "progress": 100,
                "details": s ? "Complete" : (message || "Failed"),
                "status": s ? "Complete" : (isCancelled ? "Cancelled" : "Failed")
            })
            var nextIndex = taskModel.count - 1
            var nextMap = Object.assign({}, rowIndex)
            nextMap[name] = nextIndex
            rowIndex = nextMap
        }
    }
    
    function addFailure(payload) {
        var name = payload.name
        if (failedIndex[name] === undefined) {
            failedModel.append({
                "name": name,
                "chapter_id": payload.chapter_id,
                "number": payload.number,
                "reason": payload.reason,
                "category": payload.category,
                "message": payload.message
            })
            var nextMap = Object.assign({}, failedIndex)
            nextMap[name] = failedModel.count - 1
            failedIndex = nextMap
            failCount = failedModel.count
            
            failedChipAnim.restart()
        }
    }
    
    function updateChapterProgress(name, current, total) {
        var i = rowIndex[name]
        if (i !== undefined && i < taskModel.count) {
            taskModel.setProperty(i, "progress", (current / total) * 100)
            taskModel.setProperty(i, "details", current + " / " + total + " images")
        } else {
            taskModel.append({
                "name": name,
                "progress": (current / total) * 100,
                "details": current + " / " + total + " images",
                "status": "Downloading"
            })
            var nextMap = Object.assign({}, rowIndex)
            nextMap[name] = taskModel.count - 1
            rowIndex = nextMap
        }
    }
    
    function setFinished(successful, failed) {
        isFinished = true
        successCount = successful
        failCount = failedModel.count // backend failed count includes cancels, so trust our model
    }
    
    function copyFailedNumbers() {
        if (!bridge) return
        var numbers = []
        for (var i = 0; i < failedModel.count; i++) {
            var n = failedModel.get(i).number
            if (n && n !== "?") numbers.push(n)
        }
        var formatted = bridge.formatChapterNumbers(numbers)
        bridge.copyToClipboard(formatted)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12
        
        // HEADER
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: isFinished ? (failCount > 0 ? "COMPLETED WITH " + failCount + " FAILURES" : "DOWNLOAD COMPLETE") : "DOWNLOADING"
                font.family: "Segoe UI"; font.pixelSize: 18; font.weight: Font.DemiBold
                color: isFinished ? (failCount > 0 ? accentPrimary : successColor) : textPrimary
            }
            Item { Layout.fillWidth: true }
            Text {
                text: completedChapters + " / " + totalChapters + " chapters"
                font.pixelSize: 12
                color: textSecondary
            }
        }
        
        // OVERALL PROGRESS BAR
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 8
            color: bgElevated
            radius: 4
            
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: totalChapters > 0 ? parent.width * (completedChapters / totalChapters) : 0
                radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: isFinished ? (failCount > 0 ? accentPrimary : successColor) : accentPrimary }
                    GradientStop { position: 1.0; color: isFinished ? (failCount > 0 ? errorColor : "#8BC34A") : accentHighlight }
                }
                Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
            }
        }
        
        // STATS CHIPS & TABS
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            
            // Success chip
            Rectangle {
                Layout.preferredHeight: 24; Layout.preferredWidth: sText.width + 16
                radius: 12; color: successCount > 0 ? "#1a3818" : bgElevated
                border.color: successCount > 0 ? successColor : bgElevated
                Text { id: sText; text: "✓ " + successCount + " done"; color: successCount > 0 ? successColor : textSecondary; font.pixelSize: 11; anchors.centerIn: parent }
            }
            // Failed chip
            Rectangle {
                id: fChip
                Layout.preferredHeight: 24; Layout.preferredWidth: fText.width + 16
                radius: 12; color: failCount > 0 ? "#3b1616" : bgElevated
                border.color: failCount > 0 ? errorColor : bgElevated
                Text { id: fText; text: "✗ " + failCount + " failed"; color: failCount > 0 ? errorColor : textSecondary; font.pixelSize: 11; anchors.centerIn: parent }
                
                SequentialAnimation on color {
                    id: failedChipAnim
                    running: false
                    ColorAnimation { to: errorColor; duration: 150 }
                    ColorAnimation { to: "#3b1616"; duration: 400 }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (failCount > 0) viewFilter = "failed"
                }
            }
            // Cancelled chip
            Rectangle {
                Layout.preferredHeight: 24; Layout.preferredWidth: cText.width + 16
                radius: 12; color: bgElevated; visible: cancelledCount > 0
                Text { id: cText; text: "⦸ " + cancelledCount + " cancelled"; color: textSecondary; font.pixelSize: 11; anchors.centerIn: parent }
            }
            
            Item { Layout.fillWidth: true }
            
            // View tabs
            RowLayout {
                spacing: 2
                Rectangle {
                    Layout.preferredHeight: 24; Layout.preferredWidth: allTabText.width + 24
                    radius: 4; color: viewFilter === "all" ? bgElevated : "transparent"
                    Text { id: allTabText; text: "All (" + taskModel.count + ")"; color: viewFilter === "all" ? textPrimary : textSecondary; font.pixelSize: 12; anchors.centerIn: parent }
                    MouseArea { anchors.fill: parent; onClicked: viewFilter = "all"; cursorShape: Qt.PointingHandCursor }
                }
                Rectangle {
                    Layout.preferredHeight: 24; Layout.preferredWidth: failTabText.width + 24
                    radius: 4; color: viewFilter === "failed" ? bgElevated : "transparent"
                    Text { id: failTabText; text: "Failed (" + failCount + ")"; color: viewFilter === "failed" ? textPrimary : textSecondary; font.pixelSize: 12; anchors.centerIn: parent }
                    MouseArea { anchors.fill: parent; onClicked: viewFilter = "failed"; cursorShape: Qt.PointingHandCursor }
                }
            }
            
            // Copy button
            Button {
                visible: failCount > 0
                text: "Copy chapter numbers"
                font.pixelSize: 11
                Layout.preferredHeight: 24
                onClicked: copyFailedNumbers()
            }
        }
        
        // ACTIVE CHAPTERS LIST
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: (viewFilter === "all" ? taskModel.count : failedModel.count) > 0
            clip: true
            
            ListView {
                model: viewFilter === "all" ? taskModel : failedModel
                spacing: 8
                
                delegate: ColumnLayout {
                    width: parent.width
                    spacing: 2
                    
                    Loader {
                        Layout.fillWidth: true
                        sourceComponent: viewFilter === "all" ? allDelegate : failedDelegate
                    }
                }
            }
        }
        
        // COMPLETION MESSAGE
        RowLayout {
            Layout.fillWidth: true
            visible: isFinished
            
            Text {
                text: failCount === 0 ? "🎉 All chapters downloaded successfully!" : "⚠️ Some chapters failed to download."
                font.pixelSize: 14
                color: failCount === 0 ? successColor : errorColor
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            
            Button {
                visible: failCount > 0 && bridge && bridge.hasFailures
                text: "Retry failed"
                onClicked: bridge.retryFailed()
            }
        }
    }
    
    Component {
        id: allDelegate
        ColumnLayout {
            spacing: 2
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: model.name
                    font.pixelSize: 12; font.weight: Font.Medium
                    color: model.status === "Failed" ? errorColor : textPrimary
                    elide: Text.ElideRight; Layout.fillWidth: true
                }
                Text {
                    text: model.details
                    font.pixelSize: 10; color: textSecondary
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 4
                color: bgElevated; radius: 2
                Rectangle {
                    height: parent.height; radius: 2
                    width: parent.width * (model.progress / 100)
                    color: model.status === "Failed" ? errorColor : (model.status === "Complete" ? successColor : (model.status === "Cancelled" ? textSecondary : accentPrimary))
                    Behavior on width { NumberAnimation { duration: 150 } }
                }
            }
        }
    }
    
    Component {
        id: failedDelegate
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: fCol.implicitHeight + 16
            color: bgElevated
            radius: 6
            border.color: "#3b1616"
            
            Rectangle {
                width: 4; anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                color: errorColor; radius: 6
            }
            
            ColumnLayout {
                id: fCol
                anchors.fill: parent; anchors.margins: 8; anchors.leftMargin: 16
                spacing: 4
                
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: model.name
                        font.pixelSize: 13; font.weight: Font.DemiBold; color: textPrimary
                        Layout.fillWidth: true; elide: Text.ElideRight
                    }
                    Rectangle {
                        color: "#3b1616"; radius: 4
                        Layout.preferredHeight: 20; Layout.preferredWidth: rText.width + 12
                        Text { id: rText; text: "⚠ " + model.reason; color: errorColor; font.pixelSize: 11; anchors.centerIn: parent }
                    }
                }
                
                TextEdit {
                    text: model.message
                    font.pixelSize: 11; color: textSecondary
                    readOnly: true; selectByMouse: true
                    wrapMode: Text.Wrap; Layout.fillWidth: true
                }
            }
        }
    }
}
