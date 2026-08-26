import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

FloatingWindow {
  id: root

  title: "Nextcloud Notes"
  color: Color.background
  visible: true
  implicitWidth: 1080
  implicitHeight: 720
  minimumSize: Qt.size(760, 520)

  readonly property string helperPath: Qt.resolvedUrl("nextcloud_client.py").toString().replace("file://", "")
  property int page: 0 // 0 login, 1 notes, 2 editor
  property bool busy: false
  property string errorMessage: ""
  property string serverUrl: ""
  property string username: ""
  property var currentNote: ({readonly: false})
  property string currentMarkdown: ""
  property bool updatingEditor: false
  property bool dirty: false
  property bool saveReturnToList: false
  property bool previewMode: false

  function command(args) { return ["python3", root.helperPath].concat(args) }
  function clearError() { errorMessage = "" }
  function output(text, fallback) {
    try { return JSON.parse(String(text).trim()) }
    catch (e) { return {ok: false, error: fallback} }
  }
  function setError(data, fallback) {
    busy = false
    if (!data.ok) errorMessage = String(data.error || fallback)
    return data.ok
  }
  function login() {
    clearError()
    if (!urlField.text.trim() || !userField.text.trim() || !passwordField.text) {
      errorMessage = "URL, username, and password are required."
      return
    }
    busy = true
    configureProc.secret = passwordField.text
    configureProc.command = command(["configure"])
    configureProc.running = true
  }
  function loadNotes() {
    if (busy) return
    busy = true; clearError()
    listProc.command = command(["list"])
    listProc.running = true
  }
  function loadCache() {
    cacheProc.command = command(["cache"])
    cacheProc.running = true
  }
  function openNote(note) {
    if (busy || !note || !note.id) return
    if (note.content !== undefined) {
      showEditor(note)
      return
    }
    var id = note.id
    busy = true; clearError()
    getProc.command = command(["get", String(id)])
    getProc.running = true
  }
  function saveNote(returnToList) {
    if (busy || currentNote.readonly) return
    busy = true; clearError()
    saveReturnToList = returnToList === true
    saveProc.payload = JSON.stringify({id: currentNote.id, title: titleField.text,
      content: bodyField.text, etag: currentNote.etag || ""})
    saveProc.command = command(["save"])
    saveProc.running = true
  }
  function showEditor(note) {
    updatingEditor = true
    currentNote = note
    page = 2
    previewMode = false
    titleField.text = note.title || ""
    bodyField.text = note.content || ""
    currentMarkdown = note.content || ""
    dirty = false
    updatingEditor = false
    Qt.callLater(function() { bodyField.forceActiveFocus() })
  }
  function showList() { page = 1 }
  function signOut() {
    page = 0; serverUrl = ""; username = ""
    urlField.text = ""; userField.text = ""; passwordField.text = ""
    clearError()
  }

  Component.onCompleted: {
    statusProc.command = command(["status"])
    statusProc.running = true
  }

  Shortcut {
    sequence: "Ctrl+S"
    enabled: root.page === 2 && !root.busy && !root.currentNote.readonly
    onActivated: root.saveNote(false)
  }

  Timer {
    interval: 30000
    repeat: true
    running: true
    onTriggered: if (root.page === 2 && root.dirty && !root.busy && !root.currentNote.readonly) root.saveNote(false)
  }

  Column {
      anchors.fill: parent
      anchors.margins: Style.space(24)
      spacing: Style.space(18)

      RowLayout {
        width: parent.width
        spacing: Style.space(12)
        Text { text: "▤"; color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.iconLarge }
        Column {
          Layout.fillWidth: true
          Text { text: "Nextcloud Notes"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
          Text { text: root.page === 0 ? "Connect your notes" : (root.username + " · " + root.serverUrl); color: Qt.darker(Color.foreground, 1.45); font.family: Style.font.family; font.pixelSize: Style.font.caption; elide: Text.ElideRight; width: parent.width }
        }
        Button { visible: root.page === 1; text: "Refresh"; bordered: true; onClicked: root.loadNotes() }
        Button { visible: root.page !== 0; text: "Sign out"; bordered: true; onClicked: root.signOut() }
      }

      Rectangle { width: parent.width; height: 1; color: Qt.alpha(Color.foreground, 0.12) }

      StackLayout { id: pages; width: parent.width; height: parent.height - y; currentIndex: root.page
        Column {
          width: parent.width; spacing: Style.space(12)
          Item { Layout.fillHeight: true }
          Column {
            width: Math.min(parent.width, Style.space(500)); anchors.horizontalCenter: parent.horizontalCenter; spacing: Style.space(10)
            Text { text: "Connect your notes"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.display; font.bold: true }
            Text { text: "Read and edit your self-hosted Nextcloud Notes."; color: Qt.darker(Color.foreground, 1.45); font.family: Style.font.family; font.pixelSize: Style.font.body }
            TextField { id: urlField; width: parent.width; placeholderText: "Nextcloud URL (http:// or https://)"; onAccepted: userField.forceActiveFocus() }
            TextField { id: userField; width: parent.width; placeholderText: "Username"; onAccepted: passwordField.forceActiveFocus() }
            TextField { id: passwordField; width: parent.width; placeholderText: "Password or app password"; password: true; onAccepted: root.login() }
            Button { width: parent.width; text: root.busy ? "Connecting…" : "Sign in"; bordered: true; onClicked: if (!root.busy) root.login() }
            Text { width: parent.width; wrapMode: Text.WordWrap; text: "HTTP is supported for trusted local networks. HTTPS is recommended on public or untrusted networks."; color: Qt.darker(Color.foreground, 1.55); font.family: Style.font.family; font.pixelSize: Style.font.caption }
          }
          Item { Layout.fillHeight: true }
        }

        ColumnLayout {
          spacing: Style.space(12)
          TextField { id: searchField; Layout.fillWidth: true; placeholderText: "Filter notes…" }
          ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            ListView {
              width: parent.width; model: notesModel; spacing: Style.space(3)
              delegate: Button {
                required property var modelData
                width: ListView.view.width; leftAlign: true; bordered: false
                visible: !searchField.text.trim() || String(modelData.title).toLowerCase().indexOf(searchField.text.trim().toLowerCase()) >= 0
                height: visible ? Style.space(60) : 0
                text: (modelData.favorite ? "★ " : "") + String(modelData.title)
                onClicked: root.openNote(modelData)
              }
            }
          }
          Text { visible: root.busy; Layout.fillWidth: true; text: "Loading notes…"; color: Qt.darker(Color.foreground, 1.45); font.family: Style.font.family; font.pixelSize: Style.font.caption }
        }

        ColumnLayout {
          spacing: Style.space(10)
          RowLayout {
            Layout.fillWidth: true; spacing: Style.space(8)
            Button { text: "‹ Notes"; bordered: true; onClicked: root.showList() }
            Item { Layout.fillWidth: true }
            Button { text: root.previewMode ? "Edit" : "Preview"; bordered: true; onClicked: root.previewMode = !root.previewMode }
            Button { text: root.busy ? "Saving…" : "Save"; bordered: true; enabled: !currentNote.readonly && !root.busy; onClicked: root.saveNote(false) }
          }
          TextField { id: titleField; Layout.fillWidth: true; placeholderText: "Note title"; enabled: !currentNote.readonly; onTextChanged: if (!root.updatingEditor) root.dirty = true }
          Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true; color: Qt.darker(Color.background, 1.08); radius: Style.cornerRadius
            ScrollView {
              id: markdownPreview
              visible: root.previewMode
              anchors.fill: parent
              anchors.margins: Style.space(12)
              clip: true
              Text {
                width: markdownPreview.width
                text: root.currentMarkdown
                textFormat: Text.MarkdownText
                wrapMode: Text.WordWrap
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                linkColor: Color.accent
              }
            }
            ScrollView {
              visible: !root.previewMode
              anchors.fill: parent
              anchors.margins: Style.space(3)
              clip: true
              TextArea {
                id: bodyField
                width: parent.width
                height: Math.max(contentHeight, parent.height)
                wrapMode: TextEdit.Wrap
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                background: null
                readOnly: currentNote.readonly
                selectByMouse: true
                leftPadding: Style.space(8)
                rightPadding: Style.space(8)
                topPadding: Style.space(8)
                bottomPadding: Style.space(8)
                onTextChanged: { root.currentMarkdown = text; if (!root.updatingEditor) root.dirty = true }
              }
            }
          }
        }
      }

      Text { visible: root.errorMessage !== ""; text: root.errorMessage; width: parent.width; wrapMode: Text.WordWrap; color: Color.urgent; font.family: Style.font.family; font.pixelSize: Style.font.caption }
  }

  ListModel { id: notesModel }

  Process {
    id: statusProc
    stdout: StdioCollector { id: statusOutput; waitForEnd: true }
    onExited: {
      var data = root.output(statusOutput.text, "Could not read Nextcloud settings.")
      if (data.configured === true) { root.serverUrl = String(data.url || ""); root.username = String(data.username || ""); root.loadCache() }
    }
  }
  Process {
    id: cacheProc
    stdout: StdioCollector { id: cacheOutput; waitForEnd: true }
    onExited: {
      var data = root.output(cacheOutput.text, "Could not read the notes cache.")
      if (data.ok && data.cached) {
        notesModel.clear(); (data.notes || []).forEach(function(note) { notesModel.append(note) })
        root.page = 1
      } else root.loadNotes()
    }
  }
  Process {
    id: configureProc; property string secret: ""; stdinEnabled: true
    onStarted: { write(JSON.stringify({url: urlField.text.trim(), username: userField.text.trim(), password: secret}) + "\n"); secret = ""; passwordField.text = ""; stdinEnabled = false }
    stdout: StdioCollector { id: configureOutput; waitForEnd: true }
    onExited: {
      var data = root.output(configureOutput.text, "Connection failed."); root.busy = false
      if (!root.setError(data, "Connection failed.")) return
      root.serverUrl = String(data.url || ""); root.username = String(data.username || ""); root.page = 1; root.loadNotes()
    }
  }
  Process {
    id: listProc
    stdout: StdioCollector { id: listOutput; waitForEnd: true }
    onExited: {
      var data = root.output(listOutput.text, "Could not load notes."); root.busy = false
      if (!root.setError(data, "Could not load notes.")) return
      notesModel.clear(); (data.notes || []).forEach(function(note) { notesModel.append(note) })
    }
  }
  Process {
    id: getProc
    stdout: StdioCollector { id: getOutput; waitForEnd: true }
    onExited: {
      var data = root.output(getOutput.text, "Could not open note."); root.busy = false
      if (!root.setError(data, "Could not open note.")) return
      root.showEditor(data.note || {})
    }
  }
  Process {
    id: saveProc; property string payload: ""; stdinEnabled: true
    onStarted: { write(payload + "\n"); payload = ""; stdinEnabled = false }
    stdout: StdioCollector { id: saveOutput; waitForEnd: true }
    onExited: {
      var data = root.output(saveOutput.text, "Could not save note."); root.busy = false
      if (!root.setError(data, "Could not save note.")) return
      root.currentNote = data.note || root.currentNote
      if (data.note) {
        for (var i = 0; i < notesModel.count; i++) {
          if (Number(notesModel.get(i).id) === Number(data.note.id)) {
            notesModel.set(i, data.note)
            break
          }
        }
      }
      root.dirty = false; root.errorMessage = "Saved"
      if (root.saveReturnToList) root.showList()
    }
  }
}
