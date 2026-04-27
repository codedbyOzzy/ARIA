import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls.Material 2.15

ApplicationWindow {
    id: root
    visible: true
    width: 960
    height: 680
    minimumWidth: 780
    minimumHeight: 520
    title: "F.R.I.D.A.Y."
    color: "#050a0f"

    // ── Bridge sinyalleri (Python tarafından çağrılır) ────────────────────────
    // bridge.addMessage(text, isUser)
    // bridge.setStatus(text)
    // bridge.setListening(bool)
    // bridge.setThinking(bool)
    // bridge.setLiveActive(bool)
    // bridge.setFallback(bool)

    // ── Renk paleti ──────────────────────────────────────────────────────────
    readonly property color cBg:        "#050a0f"
    readonly property color cPanel:     "#06111e"
    readonly property color cBorder:    "#0a2a4a"
    readonly property color cAccent:    "#00aaff"
    readonly property color cAccent2:   "#00ffcc"
    readonly property color cUserMsg:   "#80d4ff"
    readonly property color cAiMsg:     "#7fffb0"
    readonly property color cDim:       "#2a4a6a"
    readonly property color cWarn:      "#ffaa44"
    readonly property color cRed:       "#ff4444"

    // ── Durum değişkenleri ────────────────────────────────────────────────────
    property bool isListening: false
    property bool isThinking:  false
    property bool isLiveActive: false
    property bool isFallback:  false
    property string statusText: "hazır"
    property real  reactorPulse: 0.0   // 0..1 reaktör nabzı

    // ── Reaktör nabız animasyonu ──────────────────────────────────────────────
    SequentialAnimation on reactorPulse {
        loops: Animation.Infinite
        NumberAnimation { to: 1.0; duration: 1800; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0.0; duration: 1800; easing.type: Easing.InOutSine }
    }

    // ── Ana layout ────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Başlık çubuğu ────────────────────────────────────────────────────
        Rectangle {
            id: headerBar
            Layout.fillWidth: true
            height: 54
            color: cPanel
            layer.enabled: true

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: cBorder
            }

            RowLayout {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                spacing: 12

                // Arc Reactor küçük ikon
                Canvas {
                    id: reactorIcon
                    width: 28; height: 28
                    property real pulse: root.reactorPulse

                    onPulseChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        var cx = width / 2, cy = height / 2
                        var glow = 0.4 + 0.6 * pulse

                        // Dış halka
                        ctx.beginPath()
                        ctx.arc(cx, cy, 12, 0, Math.PI * 2)
                        ctx.strokeStyle = Qt.rgba(0, 0.67, 1, glow)
                        ctx.lineWidth = 1.5
                        ctx.stroke()

                        // İç halka
                        ctx.beginPath()
                        ctx.arc(cx, cy, 7, 0, Math.PI * 2)
                        ctx.strokeStyle = Qt.rgba(0, 1, 0.8, glow * 0.9)
                        ctx.lineWidth = 1
                        ctx.stroke()

                        // Merkez nokta
                        var grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 5)
                        grad.addColorStop(0, Qt.rgba(0, 1, 1, glow))
                        grad.addColorStop(1, Qt.rgba(0, 0.5, 1, 0))
                        ctx.beginPath()
                        ctx.arc(cx, cy, 4, 0, Math.PI * 2)
                        ctx.fillStyle = grad
                        ctx.fill()

                        // 3 trifold çizgi
                        for (var i = 0; i < 3; i++) {
                            var angle = (i * 120 - 90) * Math.PI / 180
                            ctx.beginPath()
                            ctx.moveTo(cx + 7 * Math.cos(angle), cy + 7 * Math.sin(angle))
                            ctx.lineTo(cx + 12 * Math.cos(angle), cy + 12 * Math.sin(angle))
                            ctx.strokeStyle = Qt.rgba(0, 0.8, 1, glow * 0.7)
                            ctx.lineWidth = 1.5
                            ctx.stroke()
                        }
                    }
                }

                Text {
                    text: "F.R.I.D.A.Y."
                    font.family: "Consolas"
                    font.pixelSize: 16
                    font.bold: true
                    color: cAccent
                    style: Text.Raised
                    styleColor: Qt.rgba(0, 0.67, 1, 0.3)
                }

                Text {
                    text: "v2"
                    font.family: "Consolas"
                    font.pixelSize: 10
                    color: cDim
                    Layout.alignment: Qt.AlignBottom
                    bottomPadding: 2
                }

                Item { Layout.fillWidth: true }

                // Durum göstergesi
                RowLayout {
                    spacing: 6
                    Rectangle {
                        width: 7; height: 7
                        radius: 3.5
                        color: {
                            if (root.isListening) return "#00ff88"
                            if (root.isThinking)  return "#ffaa00"
                            if (root.isLiveActive) return "#00ffcc"
                            return cDim
                        }
                        Behavior on color { ColorAnimation { duration: 200 } }

                        SequentialAnimation on opacity {
                            running: root.isListening || root.isThinking
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.3; duration: 400 }
                            NumberAnimation { to: 1.0; duration: 400 }
                        }
                        opacity: (root.isListening || root.isThinking) ? 1.0 : 0.6
                    }

                    Text {
                        id: statusLabel
                        text: root.statusText
                        font.family: "Consolas"
                        font.pixelSize: 10
                        color: cDim
                    }
                }

                // Fallback göstergesi
                Rectangle {
                    visible: root.isFallback
                    width: fallbackText.implicitWidth + 12
                    height: 20
                    radius: 3
                    color: Qt.rgba(1, 0.67, 0.27, 0.15)
                    border.color: cWarn
                    border.width: 1

                    Text {
                        id: fallbackText
                        anchors.centerIn: parent
                        text: "OpenAI"
                        font.family: "Consolas"
                        font.pixelSize: 9
                        color: cWarn
                    }
                }
            }
        }

        // ── İçerik alanı ─────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ── Sol panel — Arc Reactor HUD ──────────────────────────────────
            Rectangle {
                id: sidePanel
                Layout.preferredWidth: 200
                Layout.fillHeight: true
                color: cPanel
                visible: root.width >= 820

                Rectangle {
                    anchors.right: parent.right
                    width: 1
                    height: parent.height
                    color: cBorder
                }

                ColumnLayout {
                    anchors { fill: parent; margins: 0 }
                    spacing: 0

                    Item { Layout.fillHeight: true }

                    // Büyük Arc Reactor canvas
                    Canvas {
                        id: bigReactor
                        Layout.alignment: Qt.AlignHCenter
                        width: 140; height: 140
                        property real pulse: root.reactorPulse
                        property bool listening: root.isListening
                        property bool thinking: root.isThinking

                        onPulseChanged:    requestPaint()
                        onListeningChanged: requestPaint()
                        onThinkingChanged:  requestPaint()

                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            var cx = width / 2, cy = height / 2
                            var p = pulse

                            // Dış parlama halesi
                            var halo = ctx.createRadialGradient(cx, cy, 40, cx, cy, 70)
                            halo.addColorStop(0, Qt.rgba(0, 0.67, 1, 0.08 * (1 + p)))
                            halo.addColorStop(1, Qt.rgba(0, 0, 0, 0))
                            ctx.beginPath()
                            ctx.arc(cx, cy, 70, 0, Math.PI * 2)
                            ctx.fillStyle = halo
                            ctx.fill()

                            // Dış dişli halka (10 diş)
                            var outerR = 58, toothH = 8, toothW = 0.18
                            ctx.strokeStyle = Qt.rgba(0, 0.67, 1, 0.35 + 0.25 * p)
                            ctx.lineWidth = 2
                            for (var t = 0; t < 10; t++) {
                                var a1 = (t * 36 - 8) * Math.PI / 180
                                var a2 = (t * 36 + 8) * Math.PI / 180
                                ctx.beginPath()
                                ctx.arc(cx, cy, outerR, a1, a2)
                                ctx.stroke()
                                // Diş
                                var amid = (a1 + a2) / 2
                                ctx.beginPath()
                                ctx.moveTo(cx + outerR * Math.cos(amid), cy + outerR * Math.sin(amid))
                                ctx.lineTo(cx + (outerR + toothH) * Math.cos(amid), cy + (outerR + toothH) * Math.sin(amid))
                                ctx.stroke()
                            }

                            // Halka 1
                            ctx.beginPath()
                            ctx.arc(cx, cy, 50, 0, Math.PI * 2)
                            ctx.strokeStyle = Qt.rgba(0, 0.67, 1, 0.5 + 0.5 * p)
                            ctx.lineWidth = 1.5
                            ctx.stroke()

                            // Halka 2
                            ctx.beginPath()
                            ctx.arc(cx, cy, 38, 0, Math.PI * 2)
                            ctx.strokeStyle = Qt.rgba(0, 1, 0.8, 0.4 + 0.4 * p)
                            ctx.lineWidth = 1
                            ctx.stroke()

                            // 3 trifold kol
                            for (var i = 0; i < 3; i++) {
                                var ang = (i * 120 - 90) * Math.PI / 180
                                ctx.beginPath()
                                ctx.moveTo(cx + 20 * Math.cos(ang), cy + 20 * Math.sin(ang))
                                ctx.lineTo(cx + 48 * Math.cos(ang), cy + 48 * Math.sin(ang))
                                ctx.strokeStyle = Qt.rgba(0, 0.8, 1, 0.6 + 0.4 * p)
                                ctx.lineWidth = 2
                                ctx.stroke()
                            }

                            // Merkez halka
                            ctx.beginPath()
                            ctx.arc(cx, cy, 18, 0, Math.PI * 2)
                            ctx.strokeStyle = Qt.rgba(0, 1, 1, 0.7 + 0.3 * p)
                            ctx.lineWidth = 2
                            ctx.stroke()

                            // Merkez dolgu (parlama)
                            var grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, 18)
                            if (listening) {
                                grd.addColorStop(0, Qt.rgba(0, 1, 0.5, 0.9))
                                grd.addColorStop(1, Qt.rgba(0, 0.5, 0.3, 0))
                            } else if (thinking) {
                                grd.addColorStop(0, Qt.rgba(1, 0.67, 0, 0.9))
                                grd.addColorStop(1, Qt.rgba(0.5, 0.3, 0, 0))
                            } else {
                                grd.addColorStop(0, Qt.rgba(0, 0.8, 1, 0.7 + 0.3 * p))
                                grd.addColorStop(1, Qt.rgba(0, 0.3, 0.6, 0))
                            }
                            ctx.beginPath()
                            ctx.arc(cx, cy, 18, 0, Math.PI * 2)
                            ctx.fillStyle = grd
                            ctx.fill()
                        }
                    }

                    // Reaktör altı durum yazısı
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: {
                            if (root.isListening) return "DİNLİYOR"
                            if (root.isThinking)  return "DÜŞÜNÜYOR"
                            if (root.isLiveActive) return "LIVE MOD"
                            return "HAZIR"
                        }
                        font.family: "Consolas"
                        font.pixelSize: 10
                        font.letterSpacing: 2
                        color: {
                            if (root.isListening) return "#00ff88"
                            if (root.isThinking)  return "#ffaa00"
                            if (root.isLiveActive) return cAccent2
                            return cDim
                        }
                        Behavior on color { ColorAnimation { duration: 300 } }
                        topPadding: 8
                    }

                    // Ses dalgası göstergesi (dinleme sırasında)
                    Canvas {
                        id: waveCanvas
                        Layout.alignment: Qt.AlignHCenter
                        width: 160; height: 40
                        visible: root.isListening
                        property real phase: 0

                        NumberAnimation on phase {
                            running: root.isListening
                            from: 0; to: Math.PI * 2
                            duration: 800
                            loops: Animation.Infinite
                        }

                        onPhaseChanged: requestPaint()

                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            ctx.beginPath()
                            ctx.strokeStyle = "#00ff88"
                            ctx.lineWidth = 1.5
                            for (var x = 0; x < width; x++) {
                                var t = x / width * Math.PI * 4 + phase
                                var amp = 12 * Math.sin(x / width * Math.PI)
                                var y = height / 2 + amp * Math.sin(t)
                                if (x === 0) ctx.moveTo(x, y)
                                else ctx.lineTo(x, y)
                            }
                            ctx.stroke()
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // Alt sistem bilgisi
                    Column {
                        Layout.fillWidth: true
                        Layout.bottomMargin: 16
                        spacing: 3
                        leftPadding: 14

                        Repeater {
                            model: [
                                { label: "STT", value: "Auto-detect" },
                                { label: "LLM", value: "Gemini 2.5" },
                                { label: "TTS", value: "edge-tts" },
                            ]
                            Row {
                                spacing: 6
                                leftPadding: 14
                                Text {
                                    text: modelData.label
                                    font.family: "Consolas"
                                    font.pixelSize: 9
                                    color: cDim
                                    font.letterSpacing: 1
                                }
                                Text {
                                    text: modelData.value
                                    font.family: "Consolas"
                                    font.pixelSize: 9
                                    color: Qt.lighter(cDim, 1.4)
                                }
                            }
                        }
                    }
                }
            }

            // ── Sohbet alanı ─────────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // Konuşma listesi
                ListView {
                    id: msgList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 6
                    leftMargin: 12
                    rightMargin: 12
                    topMargin: 12
                    bottomMargin: 6

                    model: ListModel { id: msgModel }

                    // Yeni mesaj gelince en alta git
                    onCountChanged: Qt.callLater(function() {
                        msgList.positionViewAtEnd()
                    })

                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        contentItem: Rectangle {
                            implicitWidth: 5
                            radius: 2.5
                            color: cBorder
                        }
                    }

                    delegate: Item {
                        width: msgList.width - msgList.leftMargin - msgList.rightMargin
                        height: bubble.height + 4

                        // Kullanıcı mesajı sağda, AI solda
                        Rectangle {
                            id: bubble
                            anchors {
                                right: model.isUser ? parent.right : undefined
                                left:  model.isUser ? undefined : parent.left
                            }
                            width: Math.min(msgText.implicitWidth + 24, parent.width * 0.82)
                            height: msgText.implicitHeight + 18
                            radius: 8
                            color: model.isUser
                                   ? Qt.rgba(0.1, 0.16, 0.23, 1)
                                   : Qt.rgba(0.04, 0.12, 0.04, 1)
                            border.color: model.isUser ? cBorder : Qt.rgba(0, 0.3, 0.1, 1)
                            border.width: 1

                            // Sol accent çizgisi (AI mesajları için)
                            Rectangle {
                                visible: !model.isUser
                                width: 2
                                height: parent.height - 10
                                anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                                color: cAccent2
                                radius: 1
                            }

                            Text {
                                id: msgText
                                anchors {
                                    left: parent.left; leftMargin: model.isUser ? 12 : 14
                                    right: parent.right; rightMargin: 12
                                    verticalCenter: parent.verticalCenter
                                }
                                text: model.text
                                wrapMode: Text.WordWrap
                                font.family: "Consolas"
                                font.pixelSize: 11
                                color: model.isUser ? cUserMsg : cAiMsg
                                lineHeight: 1.3
                                textFormat: Text.PlainText
                            }
                        }
                    }
                }

                // "Düşünüyor" animasyonu
                Rectangle {
                    visible: root.isThinking
                    Layout.alignment: Qt.AlignLeft
                    Layout.leftMargin: 16
                    Layout.bottomMargin: 4
                    width: thinkRow.implicitWidth + 16
                    height: 28
                    radius: 6
                    color: Qt.rgba(0.04, 0.12, 0.04, 1)
                    border.color: Qt.rgba(0, 0.3, 0.1, 1)
                    border.width: 1

                    RowLayout {
                        id: thinkRow
                        anchors.centerIn: parent
                        spacing: 5

                        Repeater {
                            model: 3
                            Rectangle {
                                width: 6; height: 6; radius: 3
                                color: cAccent2

                                SequentialAnimation on opacity {
                                    running: root.isThinking
                                    loops: Animation.Infinite
                                    PauseAnimation { duration: index * 200 }
                                    NumberAnimation { to: 0.2; duration: 300 }
                                    NumberAnimation { to: 1.0; duration: 300 }
                                    PauseAnimation { duration: (2 - index) * 200 }
                                }
                            }
                        }

                        Text {
                            text: "F.R.I.D.A.Y. işliyor…"
                            font.family: "Consolas"
                            font.pixelSize: 10
                            color: Qt.lighter(cDim, 1.3)
                        }
                    }
                }

                // ── Girdi çubuğu ─────────────────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    height: 68
                    color: cPanel

                    Rectangle {
                        anchors.top: parent.top
                        width: parent.width
                        height: 1
                        color: cBorder
                    }

                    RowLayout {
                        anchors { fill: parent; leftMargin: 12; rightMargin: 12; topMargin: 10; bottomMargin: 10 }
                        spacing: 8

                        // Metin girişi
                        Rectangle {
                            Layout.fillWidth: true
                            height: 44
                            radius: 6
                            color: "#08182a"
                            border.color: inputField.activeFocus ? cAccent : cBorder
                            border.width: 1

                            Behavior on border.color { ColorAnimation { duration: 150 } }

                            TextInput {
                                id: inputField
                                anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                                verticalAlignment: TextInput.AlignVCenter
                                font.family: "Consolas"
                                font.pixelSize: 12
                                color: "#c8e8ff"
                                selectionColor: Qt.rgba(0, 0.67, 1, 0.3)
                                clip: true
                                enabled: !root.isThinking

                                Keys.onReturnPressed: bridge.sendText(text)
                                onAccepted: { bridge.sendText(text); text = "" }

                                Text {
                                    anchors.fill: parent
                                    verticalAlignment: Text.AlignVCenter
                                    text: "Komut yaz veya mikrofona bas… (Ctrl+L)"
                                    font: inputField.font
                                    color: "#2a4a6a"
                                    visible: !inputField.text && !inputField.activeFocus
                                }
                            }
                        }

                        // Gönder butonu
                        HudButton {
                            text: "Gönder"
                            width: 76
                            accent: cAccent
                            enabled: !root.isThinking
                            onClicked: { bridge.sendText(inputField.text); inputField.text = "" }
                        }

                        // Mikrofon butonu
                        HudButton {
                            id: micBtn
                            text: root.isListening ? "⏹ Dur" : "🎤 Dinle"
                            width: 86
                            accent: root.isListening ? cRed : "#00aa55"
                            onClicked: bridge.toggleListen()
                            shortcut: "Ctrl+L"
                        }

                        // Live butonu
                        HudButton {
                            text: root.isLiveActive ? "⏹ Live" : "⚡ Live"
                            width: 76
                            accent: root.isLiveActive ? cWarn : "#443300"
                            onClicked: bridge.toggleLive()
                            shortcut: "Ctrl+Shift+L"
                        }

                        // Sıfırla butonu
                        HudButton {
                            text: "↺"
                            width: 36
                            accent: "#222"
                            onClicked: bridge.resetChat()
                            shortcut: "Ctrl+R"
                        }
                    }
                }
            }
        }
    }

    // ── Python → QML API ─────────────────────────────────────────────────────
    function addMessage(text, isUser) {
        msgModel.append({ "text": text, "isUser": isUser })
    }

    function setStatus(text) {
        root.statusText = text
        statusLabel.text = text
    }

    function setListening(val) {
        root.isListening = val
    }

    function setThinking(val) {
        root.isThinking = val
    }

    function setLiveActive(val) {
        root.isLiveActive = val
    }

    function setFallback(val) {
        root.isFallback = val
    }

    function clearInput() {
        inputField.text = ""
    }

    function clearMessages() {
        msgModel.clear()
    }

    // ── HudButton bileşeni ────────────────────────────────────────────────────
    component HudButton: Rectangle {
        id: btn
        property string text: ""
        property color accent: cAccent
        property string shortcut: ""
        property bool enabled: true
        signal clicked()

        height: 44
        radius: 6
        color: hov.containsMouse ? Qt.lighter(accent, 1.3) : Qt.rgba(
            Qt.color(accent).r * 0.3,
            Qt.color(accent).g * 0.3,
            Qt.color(accent).b * 0.3,
            1
        )
        border.color: accent
        border.width: 1
        opacity: enabled ? 1.0 : 0.4

        Behavior on color { ColorAnimation { duration: 100 } }

        Text {
            anchors.centerIn: parent
            text: btn.text
            font.family: "Consolas"
            font.pixelSize: 10
            color: "#c8e8ff"
        }

        MouseArea {
            id: hov
            anchors.fill: parent
            hoverEnabled: true
            enabled: btn.enabled
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }

        Shortcut {
            sequence: btn.shortcut
            enabled: btn.shortcut !== ""
            onActivated: btn.clicked()
        }
    }
}
