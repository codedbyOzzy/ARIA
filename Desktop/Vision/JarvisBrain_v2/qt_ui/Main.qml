import QtQuick 2.15
import QtQuick.Controls 2.15

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 820
    minimumWidth: 960
    minimumHeight: 620
    title: "F.R.I.D.A.Y."
    color: "#030811"

    property bool isListening: false
    property bool isThinking: false
    property bool isLiveActive: false
    property bool isMuted: false
    property bool isSpeaking: false
    property bool isFallback: false
    property bool isSleeping: false
    property bool isConnecting: false
    property string statusText: "idle"

    property real timeValue: 0
    property real cameraAngle: 0
    property real energySeed: 0
    property bool commandOpen: false
    property real audioLevel: isMuted ? 0.08 : (isSpeaking ? 1.0 : (isThinking ? 0.72 : (isListening ? 0.50 : 0.18)))
    property real listenLevel: (isListening && !isMuted) ? 1.0 : 0.0
    property real thinkLevel: (isThinking && !isMuted) ? 1.0 : 0.0
    property real speakLevel: (isSpeaking && !isMuted) ? 1.0 : 0.0
    property real mutedLevel: isMuted ? 1.0 : 0.0
    property real memorySpark: memoryTimer.running ? 1.0 : 0.0
    property real coreR: isMuted ? 1.0 : (isThinking ? 0.44 : (isSpeaking ? 0.78 : 0.10))
    property real coreG: isMuted ? 0.55 : (isThinking ? 0.64 : (isSpeaking ? 0.98 : 0.86))
    property real coreB: isMuted ? 0.14 : (isThinking ? 1.0 : 1.0)

    Behavior on listenLevel { NumberAnimation { duration: 520; easing.type: Easing.InOutSine } }
    Behavior on thinkLevel { NumberAnimation { duration: 460; easing.type: Easing.InOutSine } }
    Behavior on speakLevel { NumberAnimation { duration: 380; easing.type: Easing.InOutSine } }
    Behavior on mutedLevel { NumberAnimation { duration: 520; easing.type: Easing.InOutSine } }

    ListModel {
        id: chatModel
        ListElement { text: "F.R.I.D.A.Y. online."; isUser: false; time: "now" }
    }

    function nowTime() {
        var d = new Date()
        return Qt.formatTime(d, "hh:mm")
    }

    function addMessage(text, isUser) {
        chatModel.append({ "text": text, "isUser": isUser, "time": nowTime() })
        if (chatModel.count > 6) chatModel.remove(0, chatModel.count - 6)
        if (!isUser) {
            pulseThinking()
            memoryTimer.restart()
        }
    }

    function clearMessages() {
        chatModel.clear()
        particleCore.reseed()
    }

    function setStatus(text) {
        statusText = String(text)
        var t = statusText.toLowerCase()
        if (t === "uyku modunda") {
            isSleeping = true
            isConnecting = false
            isListening = false
            isThinking = false
            isSpeaking = false
        } else if (t === "bağlanıyor…" || t === "yeniden bağlanıyor…") {
            isConnecting = true
            isSleeping = false
            isListening = false
            isThinking = false
        } else if (t === "dinliyor" || t === "listening") {
            isConnecting = false
            isSleeping = false
            isListening = true
            isThinking = false
        } else if (t.indexOf("düşünüyor") >= 0 || t === "thinking") {
            isConnecting = false
            isSleeping = false
            isThinking = true
        } else if (t === "hazır" || t === "idle" || t === "ready" || t === "sıfırlandı") {
            isConnecting = false
            isThinking = false
        }
    }

    function setListening(value) {
        isListening = value
    }

    function setThinking(value) {
        isThinking = value
        if (value) pulseThinking()
    }

    function setLiveActive(value) {
        isLiveActive = value
        if (value) isListening = true
    }

    function setMuted(value) {
        isMuted = value
    }

    function setSpeaking(value) {
        isSpeaking = value
        if (!value && isLiveActive) isListening = true
    }

    function setFallback(value) {
        isFallback = value
    }

    function pulseThinking() {
        energySeed = Math.random() * 1000
        burstTimer.restart()
    }

    function openCommand() {
        commandOpen = true
        commandInput.forceActiveFocus()
    }

    function closeCommand() {
        commandInput.text = ""
        commandOpen = false
        keyboardLayer.forceActiveFocus()
    }

    function submitCommand() {
        var text = commandInput.text.trim()
        if (!text) {
            closeCommand()
            return
        }
        addMessage(text, true)
        commandInput.text = ""
        commandOpen = false
        keyboardLayer.forceActiveFocus()
        bridge.sendText(text)
    }

    Timer {
        id: animationClock
        interval: 33
        running: true
        repeat: true
        onTriggered: {
            root.timeValue += interval / 1000
            root.cameraAngle += 0.0025 + root.audioLevel * 0.0018
            particleCore.requestPaint()
            hazeLayer.requestPaint()
        }
    }

    Timer {
        id: burstTimer
        interval: 1200
        repeat: false
    }

    Timer {
        id: memoryTimer
        interval: 900
        repeat: false
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#071321" }
            GradientStop { position: 0.48; color: "#030811" }
            GradientStop { position: 1.0; color: "#01040a" }
        }
    }

    Canvas {
        id: hazeLayer
        anchors.fill: parent
        opacity: 0.8

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)

            var cx = width * (0.48 + Math.sin(root.timeValue * 0.15) * 0.015)
            var cy = height * (0.48 + Math.cos(root.timeValue * 0.13) * 0.012)
            var radius = Math.min(width, height) * (0.54 + root.audioLevel * 0.11)

            var glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius)
            glow.addColorStop(0.0, Qt.rgba(root.coreR, root.coreG, root.coreB, 0.12 + root.audioLevel * 0.07 + root.memorySpark * 0.08))
            glow.addColorStop(0.32, Qt.rgba(root.coreR * 0.16, root.coreG * 0.30, root.coreB * 0.55, 0.075 + root.memorySpark * 0.035))
            glow.addColorStop(1.0, Qt.rgba(0.0, 0.0, 0.0, 0.0))
            ctx.fillStyle = glow
            ctx.fillRect(0, 0, width, height)

            var purple = ctx.createRadialGradient(width * 0.58, height * 0.38, 0, width * 0.58, height * 0.38, radius * 0.9)
            purple.addColorStop(0, Qt.rgba(0.45, 0.22, 0.9, root.isThinking || root.memorySpark > 0 ? 0.075 : (root.isFallback ? 0.08 : 0.025)))
            purple.addColorStop(1, Qt.rgba(0, 0, 0, 0))
            ctx.fillStyle = purple
            ctx.fillRect(0, 0, width, height)
        }
    }

    Canvas {
        id: particleCore
        anchors.fill: parent
        antialiasing: true

        property var particles: []
        property int particleCount: 1450
        property real burstPower: burstTimer.running ? 1.0 : 0.0
        property real thinkingFocusX: Math.sin(root.energySeed) * 0.55
        property real thinkingFocusY: Math.cos(root.energySeed * 1.7) * 0.32

        Component.onCompleted: reseed()
        onWidthChanged: reseed()
        onHeightChanged: reseed()

        function randomRange(min, max) {
            return min + Math.random() * (max - min)
        }

        function mix(a, b, amount) {
            return a + (b - a) * Math.max(0, Math.min(1, amount))
        }

        function reseed() {
            particles = []
            var count = Math.max(760, Math.min(particleCount, Math.floor(width * height / 660)))
            for (var i = 0; i < count; i++) {
                var side = i % 2 === 0 ? -1 : 1
                var cluster = Math.random()
                var angle = randomRange(0, Math.PI * 2)
                var radius = Math.pow(Math.random(), 0.52)
                var lobeBias = cluster < 0.46 ? -0.62 : (cluster > 0.56 ? 0.62 : randomRange(-0.12, 0.12))
                var baseX = lobeBias + Math.cos(angle) * radius * randomRange(0.10, 0.52)
                var baseY = Math.sin(angle * 1.15) * radius * randomRange(0.18, 0.66) + randomRange(-0.05, 0.05)
                var baseZ = randomRange(-0.62, 0.62) + side * randomRange(0, 0.10)
                var norm = Math.max(0.001, Math.sqrt(baseX * baseX + baseY * baseY + baseZ * baseZ))
                var shellScale = 0.54 + randomRange(-0.06, 0.10)
                var spiralAngle = angle + radius * 5.8 + side * 0.7
                var spiralRadius = 0.12 + radius * 0.62
                var streamT = i / count
                var streamX = -0.80 + streamT * 1.60
                var streamY = Math.sin(streamT * Math.PI * 4.0 + side) * 0.18 + randomRange(-0.06, 0.06)
                var streamZ = Math.cos(streamT * Math.PI * 3.0 + side) * 0.28 + randomRange(-0.08, 0.08)

                particles.push({
                    baseX: baseX,
                    baseY: baseY,
                    baseZ: baseZ,
                    shellX: (baseX / norm) * shellScale * 1.05,
                    shellY: (baseY / norm) * shellScale * 0.72,
                    shellZ: (baseZ / norm) * shellScale,
                    spiralX: Math.cos(spiralAngle) * spiralRadius,
                    spiralY: Math.sin(spiralAngle) * spiralRadius * 0.62,
                    spiralZ: (radius - 0.5) * 0.72 + Math.sin(spiralAngle * 0.7) * 0.10,
                    streamX: streamX,
                    streamY: streamY,
                    streamZ: streamZ,
                    phase: randomRange(0, Math.PI * 2),
                    speed: randomRange(0.45, 1.6),
                    size: randomRange(0.55, 2.15),
                    hot: Math.random() > 0.86,
                    drift: randomRange(-1, 1),
                    layer: Math.random()
                })
            }
            requestPaint()
        }

        function project(p) {
            var t = root.timeValue
            var speak = root.speakLevel
            var think = root.thinkLevel
            var listen = root.listenLevel
            var muted = root.mutedLevel
            var idleBreath = Math.sin(t * 1.1) * 0.035
            var wave = Math.sin(t * (1.4 + p.speed) + p.phase)
            var neural = Math.sin(t * 2.1 + p.baseX * 7.0 + p.baseZ * 4.0)
            var distFromCenter = Math.sqrt(p.baseX * p.baseX + p.baseY * p.baseY + p.baseZ * p.baseZ)
            var speakWave = Math.sin(distFromCenter * 6.8 - t * 3.2 + p.phase)
            var speakFlow = Math.sin(t * 2.4 + p.phase + p.baseY * 3.2)
            var listenWave = Math.sin(distFromCenter * 9.5 + t * 4.8 - p.phase)
            var focusDx = p.baseX - thinkingFocusX
            var focusDy = p.baseY - thinkingFocusY
            var focus = Math.exp(-(focusDx * focusDx + focusDy * focusDy) * 7.5)
            var memoryDx = p.baseX + Math.sin(root.energySeed * 0.37) * 0.38
            var memoryDy = p.baseY - Math.cos(root.energySeed * 0.51) * 0.24
            var memoryFocus = root.memorySpark * Math.exp(-(memoryDx * memoryDx + memoryDy * memoryDy) * 10.0)
            var travelingSpark = Math.exp(-Math.abs(Math.sin(t * 1.6 + p.phase + p.baseX * 4.0)) * 4.0) * focus
            var burst = burstPower * focus + memoryFocus * 0.55
            var formX = p.baseX
            var formY = p.baseY
            var formZ = p.baseZ
            formX = mix(formX, p.spiralX, listen * 0.72)
            formY = mix(formY, p.spiralY, listen * 0.72)
            formZ = mix(formZ, p.spiralZ, listen * 0.72)
            formX = mix(formX, p.shellX, speak * 0.54)
            formY = mix(formY, p.shellY, speak * 0.54)
            formZ = mix(formZ, p.shellZ, speak * 0.54)
            var streamBlend = think * (0.22 + focus * 0.62)
            formX = mix(formX, p.streamX, streamBlend)
            formY = mix(formY, p.streamY, streamBlend)
            formZ = mix(formZ, p.streamZ, streamBlend)
            formX = mix(formX, p.baseX * 0.68, muted * 0.75)
            formY = mix(formY, p.baseY * 0.68, muted * 0.75)
            formZ = mix(formZ, p.baseZ * 0.68, muted * 0.75)

            var activity = 1.0
                + idleBreath
                + root.audioLevel * 0.08
                + speak * speakWave * 0.045
                + listen * listenWave * 0.045
                + think * neural * 0.04
                + think * travelingSpark * 0.16
                + memoryFocus * 0.22
                + burst * 0.16
                - muted * 0.10

            var orbit = t * (0.18 + p.layer * 0.16) + p.phase
            var livingFlowX = Math.sin(orbit + p.baseY * 5.0) * (0.010 + p.layer * 0.012)
            var livingFlowY = Math.cos(orbit * 0.9 + p.baseZ * 4.0) * (0.010 + p.layer * 0.010)
            var spiral = Math.atan2(formY, formX) + t * 2.4 + p.phase
            var spiralStrength = listen * (0.018 + (1.0 - Math.min(1.0, distFromCenter)) * 0.026)
            var x = formX * activity
                + livingFlowX
                + Math.sin(t * p.speed + p.phase) * (0.016 + speak * 0.010)
                + think * focus * Math.sin(t * 5.0 + p.phase) * 0.050
                + listen * Math.cos(spiral) * spiralStrength
                + speak * Math.cos(speakFlow + p.baseZ) * 0.018
            var y = formY * activity
                + livingFlowY
                + Math.cos(t * p.speed * 0.9 + p.phase) * (0.016 + think * 0.020)
                + speak * speakWave * 0.010
                + listen * Math.sin(spiral) * spiralStrength
                + speak * Math.sin(speakFlow) * 0.016
            var z = formZ
                + Math.sin(t * 0.8 + p.phase) * 0.09
                + speak * Math.sin(t * 2.9 + p.phase) * 0.028
                + think * travelingSpark * 0.08
                + memoryFocus * Math.sin(t * 6.0 + p.phase) * 0.05
                + listen * listenWave * 0.030

            var ca = Math.cos(root.cameraAngle)
            var sa = Math.sin(root.cameraAngle)
            var rx = x * ca - z * sa
            var rz = x * sa + z * ca

            var scale = Math.min(width, height) * (0.385 + root.audioLevel * 0.048)
            var depth = 1.0 / (1.42 - rz * 0.36)
            return {
                x: width * 0.50 + rx * scale * depth,
                y: height * 0.48 + y * scale * depth,
                z: rz,
                depth: depth,
                alpha: Math.max(0.12, Math.min(1.0, 0.32 + depth * 0.42 + (p.hot ? 0.24 : 0) + focus * think * 0.30 + memoryFocus * 0.42 + burst * 0.34)),
                size: p.size * depth * (1.08 + root.audioLevel * 0.28 + speak * Math.max(0, speakWave) * 0.24 + listen * Math.max(0, listenWave) * 0.36 + focus * think * 0.88 + memoryFocus * 1.15 + burst * 0.90 - muted * 0.20),
                hot: p.hot || burst > 0.30 || memoryFocus > 0.24 || (think && focus > 0.50) || (speak && speakWave > 0.88 && p.layer > 0.72) || (listen && listenWave > 0.86),
                focus: focus,
                memoryFocus: memoryFocus,
                speakWave: speakWave,
                listenWave: listenWave,
                spark: travelingSpark
            }
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)

            if (!particles || particles.length === 0) return

            var projected = []
            for (var i = 0; i < particles.length; i++) {
                projected.push(project(particles[i]))
            }

            ctx.globalCompositeOperation = "lighter"

            if (root.isSpeaking) {
                var cx = width * 0.50
                var cy = height * 0.48
                var breath = 0.5 + 0.5 * Math.sin(root.timeValue * 2.25)
                for (var aura = 0; aura < 2; aura++) {
                    var rr = Math.min(width, height) * (0.18 + aura * 0.08 + breath * 0.018)
                    ctx.beginPath()
                    ctx.arc(cx, cy, rr, 0, Math.PI * 2)
                    ctx.strokeStyle = Qt.rgba(root.coreR, root.coreG, root.coreB, 0.025 + breath * 0.030)
                    ctx.lineWidth = 0.65 + aura * 0.25
                    ctx.stroke()
                }
            }

            if (root.isListening && !root.isMuted && !root.isSpeaking && !root.isThinking) {
                var lcx = width * 0.50
                var lcy = height * 0.48
                for (var intake = 0; intake < 3; intake++) {
                    var intakePhase = (root.timeValue * 0.45 + intake * 0.33) % 1.0
                    var ir = Math.min(width, height) * (0.38 - intakePhase * 0.22)
                    ctx.beginPath()
                    ctx.arc(lcx, lcy, ir, Math.PI * 0.18 + root.timeValue, Math.PI * 1.34 + root.timeValue)
                    ctx.strokeStyle = Qt.rgba(0.0, 0.95, 1.0, intakePhase * 0.10)
                    ctx.lineWidth = 0.8 + intakePhase * 1.1
                    ctx.stroke()
                }
            }

            if (root.isMuted) {
                var mcx = width * 0.50
                var mcy = height * 0.48
                ctx.beginPath()
                ctx.arc(mcx, mcy, Math.min(width, height) * 0.22, 0, Math.PI * 2)
                ctx.strokeStyle = Qt.rgba(1.0, 0.52, 0.14, 0.08 + Math.sin(root.timeValue * 1.2) * 0.025)
                ctx.lineWidth = 1.2
                ctx.stroke()
            }

            var stride = root.isSpeaking || root.isThinking ? 12 : 18
            for (var a = 0; a < projected.length; a += stride) {
                var p1 = projected[a]
                var p2 = projected[(a * 7 + 31) % projected.length]
                var dx = p1.x - p2.x
                var dy = p1.y - p2.y
                var d2 = dx * dx + dy * dy
                if (d2 < 14500) {
                    var lineAlpha = (1 - d2 / 14500) * (root.isThinking ? 0.25 : 0.12)
                    ctx.beginPath()
                    ctx.moveTo(p1.x, p1.y)
                    ctx.lineTo(p2.x, p2.y)
                    ctx.strokeStyle = Qt.rgba(root.coreR * 0.45 + 0.05, root.coreG, root.coreB, lineAlpha)
                    ctx.lineWidth = root.isThinking ? 0.85 : 0.45
                    ctx.stroke()
                }
            }

            if (root.isThinking) {
                var hotPoints = []
                for (var h = 0; h < projected.length; h += 17) {
                    if (projected[h].focus > 0.42 || projected[h].spark > 0.18) hotPoints.push(projected[h])
                    if (hotPoints.length >= 18) break
                }
                for (var hp = 1; hp < hotPoints.length; hp++) {
                    ctx.beginPath()
                    ctx.moveTo(hotPoints[hp - 1].x, hotPoints[hp - 1].y)
                    ctx.lineTo(hotPoints[hp].x, hotPoints[hp].y)
                    ctx.strokeStyle = Qt.rgba(0.58, 0.76, 1.0, 0.24 + hotPoints[hp].spark * 0.40)
                    ctx.lineWidth = 1.1
                    ctx.stroke()
                }
            }

            for (var j = 0; j < projected.length; j++) {
                var p = projected[j]
                var s = p.size
                var alpha = p.alpha
                var heat = p.hot ? 1.0 : 0.0
                var whiteMix = root.isSpeaking ? Math.max(0, p.speakWave) * 0.28 : 0.0
                var violetMix = root.isThinking ? p.focus * 0.32 : 0.0
                var amberMix = root.isMuted ? 0.45 : 0.0
                var memoryMix = p.memoryFocus * 0.65
                var rr = root.coreR * (0.72 + heat * 0.20) + whiteMix + violetMix * 0.35 + amberMix + memoryMix * 0.25
                var gg = root.coreG * (0.76 + heat * 0.16) + whiteMix + memoryMix * 0.20
                var bb = root.coreB * (0.82 + heat * 0.12) + whiteMix + violetMix * 0.30 + memoryMix * 0.34
                ctx.fillStyle = Qt.rgba(Math.min(1, rr), Math.min(1, gg), Math.min(1, bb), alpha)
                ctx.fillRect(p.x, p.y, s, s)

                if (p.hot && (j % 4 === 0)) {
                    ctx.beginPath()
                    ctx.arc(p.x, p.y, s * (root.isThinking ? 3.6 : 2.8), 0, Math.PI * 2)
                    ctx.fillStyle = Qt.rgba(
                        root.isMuted ? 1.0 : (root.isThinking ? 0.45 : root.coreR),
                        root.isMuted ? 0.56 : root.coreG,
                        root.isMuted ? 0.18 : root.coreB,
                        0.045 + root.audioLevel * 0.025 + p.focus * 0.035 + p.memoryFocus * 0.050
                    )
                    ctx.fill()
                }
            }

            ctx.globalCompositeOperation = "source-over"
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: {
            keyboardLayer.forceActiveFocus()
            if (mouse.button === Qt.RightButton) {
                root.setThinking(!root.isThinking)
            } else {
                root.openCommand()
            }
        }
        onDoubleClicked: {
            root.pulseThinking()
        }
    }

    Item {
        id: keyboardLayer
        anchors.fill: parent
        focus: true
        Component.onCompleted: forceActiveFocus()

        Keys.onPressed: function(event) {
            if ((event.key === Qt.Key_K && (event.modifiers & Qt.ControlModifier)) || event.text === "/") {
                root.openCommand()
                event.accepted = true
            } else if (event.key === Qt.Key_Escape && root.commandOpen) {
                root.closeCommand()
                event.accepted = true
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 0
        opacity: 0.10
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0.35, 0.65, 1.0, 0.10) }
            GradientStop { position: 0.5; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(0.0, 0.0, 0.0, 0.22) }
        }
    }

    Rectangle {
        id: chatTrace
        width: Math.min(480, root.width * 0.40)
        height: 170
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 44
        anchors.bottomMargin: 44
        radius: 24
        color: Qt.rgba(0.018, 0.052, 0.085, 0.42)
        border.width: 1
        border.color: Qt.rgba(0.28, 0.82, 1.0, 0.22)
        opacity: chatModel.count > 0 ? 1 : 0

        Behavior on opacity { NumberAnimation { duration: 260 } }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 21
            color: "transparent"
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.15, 0.55, 0.85, 0.045) }
                GradientStop { position: 1.0; color: Qt.rgba(0.0, 0.0, 0.0, 0.0) }
            }
        }

        Text {
            id: traceTitle
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 18
            anchors.topMargin: 14
            text: "thought stream"
            font.family: "Consolas"
            font.pixelSize: 11
            font.letterSpacing: 2.2
            color: Qt.rgba(0.66, 0.94, 1.0, 0.58)
        }

        ListView {
            id: traceList
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: traceTitle.bottom
            anchors.bottom: parent.bottom
            anchors.margins: 18
            anchors.topMargin: 10
            clip: true
            spacing: 6
            interactive: false
            model: chatModel
            verticalLayoutDirection: ListView.BottomToTop

            delegate: Text {
                width: traceList.width
                text: (model.isUser ? "you  " : "core ") + model.text
                elide: Text.ElideRight
                maximumLineCount: 1
                font.family: "Consolas"
                font.pixelSize: 13
                color: model.isUser ? Qt.rgba(1.0, 0.72, 0.36, 0.72) : Qt.rgba(0.72, 0.97, 1.0, 0.78)
            }
        }
    }

    Rectangle {
        id: micControl
        width: 168
        height: 50
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 44
        anchors.bottomMargin: 112
        radius: 24
        color: Qt.rgba(0.018, 0.052, 0.085, 0.46)
        border.width: 1
        border.color: root.isMuted ? Qt.rgba(1.0, 0.52, 0.16, 0.48) : Qt.rgba(0.28, 0.82, 1.0, 0.30)

        Behavior on border.color { ColorAnimation { duration: 180 } }

        Rectangle {
            id: micOrb
            width: 18
            height: 18
            radius: 9
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 18
            color: root.isMuted ? "#ff8c00" : "#00f5ff"
            opacity: root.isMuted ? 0.85 : 0.95

            SequentialAnimation on opacity {
                running: !root.isMuted && (root.isListening || root.isLiveActive)
                loops: Animation.Infinite
                NumberAnimation { to: 0.42; duration: 520 }
                NumberAnimation { to: 1.0; duration: 520 }
            }
        }

        Text {
            anchors.left: micOrb.right
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: root.isMuted ? "mic muted" : "mic active"
            font.family: "Consolas"
            font.pixelSize: 13
            font.letterSpacing: 1.5
            color: root.isMuted ? Qt.rgba(1.0, 0.66, 0.32, 0.84) : Qt.rgba(0.72, 0.97, 1.0, 0.84)
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                bridge.toggleMute()
            }
        }
    }

    Text {
        id: statusDisplay
        anchors.right: parent.right
        anchors.bottom: micControl.top
        anchors.rightMargin: 44
        anchors.bottomMargin: 10
        text: root.statusText
        font.family: "Consolas"
        font.pixelSize: 11
        font.letterSpacing: 1.8
        color: root.isMuted ? Qt.rgba(1.0, 0.66, 0.32, 0.60)
             : root.isThinking ? Qt.rgba(0.58, 0.76, 1.0, 0.72)
             : root.isSpeaking ? Qt.rgba(0.72, 0.97, 1.0, 0.72)
             : Qt.rgba(0.50, 0.80, 1.0, 0.44)
    }

    // ── Uyku / Bağlanma bildirim bandı ───────────────────────────────────────
    Rectangle {
        id: statusBanner
        visible: root.isSleeping || root.isConnecting
        width: 260
        height: 38
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 22
        radius: 19
        color: root.isSleeping ? Qt.rgba(0.06, 0.04, 0.02, 0.72)
                               : Qt.rgba(0.02, 0.06, 0.12, 0.72)
        border.width: 1
        border.color: root.isSleeping ? Qt.rgba(1.0, 0.55, 0.15, 0.45)
                                      : Qt.rgba(0.28, 0.82, 1.0, 0.55)

        Behavior on border.color { ColorAnimation { duration: 300 } }
        Behavior on color       { ColorAnimation { duration: 300 } }

        // Bağlanırken sol tarafta dönen nokta
        Rectangle {
            id: spinDot
            visible: root.isConnecting
            width: 8; height: 8; radius: 4
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            color: "#00f5ff"

            SequentialAnimation on opacity {
                running: root.isConnecting
                loops: Animation.Infinite
                NumberAnimation { to: 0.2; duration: 400 }
                NumberAnimation { to: 1.0; duration: 400 }
            }
        }

        // Uyku modunda ay simgesi yerine küçük orb
        Rectangle {
            id: sleepOrb
            visible: root.isSleeping
            width: 8; height: 8; radius: 4
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            color: "#ff8c00"
            opacity: 0.80
        }

        Text {
            anchors.left: spinDot.visible ? spinDot.right : sleepOrb.right
            anchors.leftMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: root.isSleeping ? "uyku modunda — konuş veya yaz"
                                  : "bağlanıyor…"
            font.family: "Consolas"
            font.pixelSize: 12
            font.letterSpacing: 1.4
            color: root.isSleeping ? Qt.rgba(1.0, 0.66, 0.32, 0.90)
                                   : Qt.rgba(0.72, 0.97, 1.0, 0.90)
        }
    }

    Rectangle {
        id: commandWhisper
        width: Math.min(560, root.width * 0.48)
        height: 54
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 42
        radius: 27
        opacity: root.commandOpen ? 1.0 : 0.0
        visible: opacity > 0.02
        color: Qt.rgba(0.018, 0.052, 0.085, 0.58)
        border.width: 1
        border.color: Qt.rgba(root.coreR, root.coreG, root.coreB, 0.36)

        Behavior on opacity { NumberAnimation { duration: 180 } }
        Behavior on border.color { ColorAnimation { duration: 180 } }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            visible: commandInput.text.length === 0
            text: "whisper a command..."
            font.family: "Consolas"
            font.pixelSize: 13
            font.letterSpacing: 1.2
            color: Qt.rgba(0.70, 0.95, 1.0, 0.32)
        }

        TextInput {
            id: commandInput
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            verticalAlignment: TextInput.AlignVCenter
            color: Qt.rgba(0.78, 0.98, 1.0, 0.88)
            selectedTextColor: "#03101a"
            selectionColor: "#00f5ff"
            font.family: "Consolas"
            font.pixelSize: 14
            clip: true

            Keys.onReturnPressed: root.submitCommand()
            Keys.onEnterPressed: root.submitCommand()
            Keys.onEscapePressed: root.closeCommand()
        }
    }
}
