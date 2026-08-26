import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Item {
  id: root

  readonly property string helperPath: Qt.resolvedUrl("nextcloud_client.py").toString().replace("file://", "")
  property int page: 0 // 0 login, 1 notes, 2 editor
  property bool busy: false
  property string errorMessage: ""
  property string serverUrl: ""
  property string username: ""
  property var currentNote: ({readonly: false})

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
  function openNote(id) {
    if (busy || !id) return
    busy = true; clearError()
    getProc.command = command(["get", String(id)])
    getProc.running = true
  }
  function saveNote() {
    if (busy || currentNote.readonly) return
    busy = true; clearError()
    saveProc.payload = JSON.stringify({id: currentNote.id, title: titleField.text,
      category: categoryField.text, content: bodyField.text, etag: currentNote.etag || ""})
    saveProc.command = command(["save"])
    saveProc.running = true
  }
  function showEditor(note) {
    currentNote = note
    page = 2
    titleField.text = note.title || ""
    categoryField.text = note.category || ""
    bodyField.text = note.content || ""
    Qt.callLater(function() { bodyField.forceActiveFocus() })
  }
  function showList() { page = 1; loadNotes() }
  function signOut() {
    page = 0; serverUrl = ""; username = ""
    urlField.text = ""; userField.text = ""; passwordField.text = ""
    clearError()
  }

  Component.onCompleted: {
    statusProc.command = command(["status"])
    statusProc.running = true
  }

  FloatingWindow {
    id: window
    title: "Nextcloud Notes"
    color: Color.background
    visible: true
    implicitWidth: 1080
    implicitHeight: 720
    minimumSize: Qt.size(760, 520)

    Column {
      anchors.fill: parent
      anchors.margins: Style.space(24)
      spacing: Style.space(18)

      Row {
        width: parent.width
        spacing: Style.space(12)
        Text { text: "▤"; color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.iconLarge }
        Column {
          width: parent.width - 170
          Text { text: "Nextcloud Notes"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
          Text { text: root.page === 0 ? "Connect your notes" : (root.username + " · " + root.serverUrl); color: Qt.darker(Color.foreground, 1.45); font.family: Style.font.family; font.pixelSize: Style.font.caption; elide: Text.ElideRight; width: parent.width }
        }
        Item { width: 1; height: 1 }
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

        Column {
          spacing: Style.space(12)
          TextField { id: searchField; width: parent.width; placeholderText: "Filter notes…" }
          ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            ListView {
              width: parent.width; model: notesModel; spacing: Style.space(3)
              delegate: Button {
                required property var modelData
                width: ListView.view.width; leftAlign: true; bordered: false
                visible: !searchField.text.trim() || String(modelData.title + " " + modelData.category).toLowerCase().indexOf(searchField.text.trim().toLowerCase()) >= 0
                height: visible ? Style.space(60) : 0
                text: (modelData.favorite ? "★ " : "") + String(modelData.title)
                tooltipText: modelData.category || "Uncategorized"
                onClicked: root.openNote(Number(modelData.id))
              }
            }
          }
          Text { visible: root.busy; text: "Loading notes…"; color: Qt.darker(Color.foreground, 1.45); font.family: Style.font.family; font.pixelSize: Style.font.caption }
        }

        Column {
          spacing: Style.space(10)
          Row {
            width: parent.width; spacing: Style.space(8)
            Button { text: "‹ Notes"; bordered: true; onClicked: root.showList() }
            Text { text: currentNote.readonly ? "Read-only" : "Edit note"; color: Qt.darker(Color.foreground, 1.45); font.family: Style.font.family; font.pixelSize: Style.font.caption; verticalAlignment: Text.AlignVCenter; Layout.fillWidth: true }
            Button { text: root.busy ? "Saving…" : "Save"; bordered: true; enabled: !currentNote.readonly && !root.busy; onClicked: root.saveNote() }
          }
          TextField { id: titleField; width: parent.width; placeholderText: "Note title"; enabled: !currentNote.readonly }
          TextField { id: categoryField; width: parent.width; placeholderText: "Category (optional)"; enabled: !currentNote.readonly }
          Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true; color: Qt.darker(Color.background, 1.08); radius: Style.cornerRadius
            TextArea { id: bodyField; anchors.fill: parent; anchors.margins: Style.space(10); wrapMode: TextEdit.Wrap; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body; background: null; readOnly: currentNote.readonly }
          }
        }
      }

      Text { visible: root.errorMessage !== ""; text: root.errorMessage; width: parent.width; wrapMode: Text.WordWrap; color: Color.urgent; font.family: Style.font.family; font.pixelSize: Style.font.caption }
    }
  }

  ListModel { id: notesModel }

  Process {
    id: statusProc
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      var data = root.output(text, "Could not read Nextcloud settings.")
      if (data.configured === true) { root.serverUrl = String(data.url || ""); root.username = String(data.username || ""); root.page = 1; root.loadNotes() }
    }}
  }
  Process {
    id: configureProc; property string secret: ""; stdinEnabled: true
    onStarted: { write(JSON.stringify({url: urlField.text.trim(), username: userField.text.trim(), password: secret}) + "\n"); secret = ""; passwordField.text = ""; stdinEnabled = false }
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      var data = root.output(text, "Connection failed."); root.busy = false
      if (!root.setError(data, "Connection failed.")) return
      root.serverUrl = String(data.url || ""); root.username = String(data.username || ""); root.page = 1; root.loadNotes()
    }}
  }
  Process {
    id: listProc
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      var data = root.output(text, "Could not load notes."); root.busy = false
      if (!root.setError(data, "Could not load notes.")) return
      notesModel.clear(); (data.notes || []).forEach(function(note) { notesModel.append(note) })
    }}
  }
  Process {
    id: getProc
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      var data = root.output(text, "Could not open note."); root.busy = false
      if (!root.setError(data, "Could not open note.")) return
      root.showEditor(data.note || {})
    }}
  }
  Process {
    id: saveProc; property string payload: ""; stdinEnabled: true
    onStarted: { write(payload + "\n"); payload = ""; stdinEnabled = false }
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {
      var data = root.output(text, "Could not save note."); root.busy = false
      if (!root.setError(data, "Could not save note.")) return
      root.currentNote = data.note || root.currentNote; root.errorMessage = "Saved"; root.showList()
    }}
  }
}
