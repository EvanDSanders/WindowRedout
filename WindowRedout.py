from PySide6.QtWidgets import (QApplication, QMainWindow, QSystemTrayIcon, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMenu,
                               QListWidget, QComboBox, QCheckBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtGui import QIcon, QCursor, QFocusEvent, QPixmap
from PySide6.QtCore import QTimer, Qt, QEvent, QFileSystemWatcher

import subprocess, time, sys, re, os, signal

from lerp import *
from X11_Module import getWindowInfo, getIdle
from QtIcons import getIcon
from Styles import *
import Config
from KWinBridge import KWinBridge

def clamp(n, min, max):
    if n < min:
        return min
    elif n > max:
        return max
    else:
        return n



class LampManager(QMainWindow):

    fac = 1

    dayTemp = 6500
    nightTemp = 2000
    idleTemp = 1550

    centerTemp = 6500
    factor = 1.0

    mode = None  # 'kwin' or 'gamma'
    forceGamma = False
    modeReason = ''
    maxRecent = 15

    lastFac  = -1
    lastTemp = 0

    def factorTemp(self, temp):
        temp -= self.centerTemp
        if self.factor != 0:
            temp = temp * self.factor
            temp += self.centerTemp
            return temp

        else:
            return self.centerTemp
            
            

    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("X11 RedLamp")
        self.hide()


        # Make the window focusable
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptDrops, False)


        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.setStyleSheet(WINDOW_STYLE)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        central_widget.setLayout(layout)
        
        self.image = QLabel()
        self.image.setPixmap(QPixmap(getIcon(6500)))
        self.image.setStyleSheet(CLEAR_STYLE)
        layout.addWidget(self.image)

  

        self.modeLabel = QLabel()
        self.modeLabel.setStyleSheet(CLEAR_STYLE)
        layout.addWidget(self.modeLabel)

        self.forceBox = QCheckBox("Force gamma ramps")
        self.forceBox.setStyleSheet(CLEAR_STYLE)
        self.forceBox.toggled.connect(self.setForceGamma)
        layout.addWidget(self.forceBox)

        self.buildRecentPanel(layout)
        self.buildConfigPanel(layout)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(QIcon(getIcon(6500, True)))
        self.trayIcon.show()
        self.trayIcon.activated.connect(self.onTrayActivated)

        self.bridge = KWinBridge()
        self.recent = []  # newest first, dicts with class/name/role

        self.entries = Config.load()
        self.fillTable()
        self.watcher = QFileSystemWatcher([Config.CONFIG_PATH])
        self.watcher.fileChanged.connect(self.onConfigFileChanged)

        # Add tray menu with quit button
        tray_menu = QMenu()
        self.forceAction = tray_menu.addAction("Force gamma ramps")
        self.forceAction.setCheckable(True)
        self.forceAction.toggled.connect(self.setForceGamma)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        quit_action = tray_menu.addAction("Reset and Quit")
        quit_action.triggered.connect(self.resetAndQuit)
        self.trayIcon.setContextMenu(tray_menu)

        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.evaluate)
        self.updateTimer.start(333)

    # ---------- UI ----------

    def buildRecentPanel(self, layout):
        title = QLabel("Recently focused")
        title.setStyleSheet(CLEAR_STYLE)
        layout.addWidget(title)

        self.recentList = QListWidget()
        self.recentList.setMinimumHeight(110)
        self.recentList.currentRowChanged.connect(self.onRecentSelected)
        layout.addWidget(self.recentList)

        row = QHBoxLayout()
        self.detectType = QComboBox()
        self.detectType.addItems(Config.DETECT_TYPES)
        self.detectType.setMinimumWidth(130)
        self.detectType.currentIndexChanged.connect(self.onRecentSelected)
        row.addWidget(self.detectType)

        self.detectValue = QLineEdit()
        row.addWidget(self.detectValue, 1)

        self.addButton = QPushButton("Add")
        self.addButton.setStyleSheet(BUTTON_STYLE)
        self.addButton.clicked.connect(self.addRecent)
        row.addWidget(self.addButton)
        layout.addLayout(row)

    def buildConfigPanel(self, layout):
        title = QLabel("Settings  (detect: type=value AND type=value)")
        title.setStyleSheet(CLEAR_STYLE)
        layout.addWidget(title)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Detect", "Dark", "Light"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setFixedHeight(40)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 55)
        self.table.setMinimumHeight(200)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        for text, slot in (("Remove", self.removeRow), ("Reload", self.reloadConfig), ("Save", self.saveConfig)):
            btn = QPushButton(text)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setStyleSheet(CLEAR_STYLE)
        layout.addWidget(self.status)

    @staticmethod
    def detectToText(detect: dict) -> str:
        return " AND ".join(f"{k}={v}" for k, v in detect.items())

    @staticmethod
    def textToDetect(text: str) -> dict:
        detect = {}
        for part in text.split(" AND "):
            if "=" not in part:
                continue
            kind, value = part.split("=", 1)
            kind = kind.strip().lower()
            if kind in Config.DETECT_TYPES and value.strip():
                detect[kind] = value.strip()
        return detect

    def fillTable(self):
        self.table.setRowCount(0)
        for entry in self.entries:
            self.appendRow(entry)

    def appendRow(self, entry: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(self.detectToText(entry["AppDetect"])))
        self.table.setItem(row, 1, QTableWidgetItem(str(entry["Dark"])))
        self.table.setItem(row, 2, QTableWidgetItem(str(entry["Light"])))

    def tableToEntries(self):
        entries = []
        for row in range(self.table.rowCount()):
            cells = [self.table.item(row, c).text() if self.table.item(row, c) else "" for c in range(3)]
            detect = self.textToDetect(cells[0])
            if not detect:
                raise ValueError(f"Row {row + 1}: no valid detection")
            try:
                dark, light = float(cells[1]), float(cells[2])
            except ValueError:
                raise ValueError(f"Row {row + 1}: Dark/Light must be numbers")
            entries.append({"AppDetect": detect, "Dark": dark, "Light": light})
        return entries

    def saveConfig(self):
        try:
            entries = self.tableToEntries()
        except ValueError as e:
            self.status.setText(str(e))
            return
        Config.save(entries)
        self.status.setText("Saved")
        # QFileSystemWatcher drops the path when editors replace the file; reload directly too
        self.reloadConfig()

    def removeRow(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def reloadConfig(self):
        self.entries = Config.load()
        self.fillTable()
        if Config.CONFIG_PATH not in self.watcher.files():
            self.watcher.addPath(Config.CONFIG_PATH)
        self.status.setText("Config loaded")

    def onConfigFileChanged(self, _path):
        QTimer.singleShot(100, self.reloadConfig)

    def trackRecent(self, info):
        if not info or not info.get("name") or info["name"] == self.windowTitle():
            return
        key = info["class"] or info["name"]
        if self.recent and self.recent[0].get("key") == key and self.recent[0]["name"] == info["name"]:
            return

        self.recent = [r for r in self.recent if r["key"] != key]
        self.recent.insert(0, dict(info, key=key))
        del self.recent[self.maxRecent:]

        current = self.recentList.currentRow()
        self.recentList.blockSignals(True)
        self.recentList.clear()
        for r in self.recent:
            cls = r["class"].split()[-1] if r["class"] else "?"
            tag = " ✓" if Config.find_entry(self.entries, r) else ""
            self.recentList.addItem(f"{cls} — {r['name']}{tag}")
        if current >= 0:
            self.recentList.setCurrentRow(min(current + 1, self.recentList.count() - 1))
        self.recentList.blockSignals(False)

    def onRecentSelected(self, *_):
        row = self.recentList.currentRow()
        if row < 0 or row >= len(self.recent):
            return
        info = self.recent[row]
        kind = self.detectType.currentText()
        if kind == "class":
            value = info["class"].split()[-1] if info["class"] else ""
        elif kind == "name":
            value = info["name"]
        elif kind == "regex":
            value = re.escape(info["name"])
        else:
            value = info["role"]
        self.detectValue.setText(value)

    def addRecent(self):
        value = self.detectValue.text().strip()
        if not value:
            self.status.setText("Pick a recent window / enter a value")
            return
        entry = {"AppDetect": {self.detectType.currentText(): value},
                 "Dark": Config.DEFAULT_DARK, "Light": Config.DEFAULT_LIGHT}
        self.appendRow(entry)
        self.table.scrollToBottom()
        self.status.setText("Added. Edit Dark/Light then Save")

    def resetAndQuit(self):
        self.bridge.unload()
        cmd = f'redshift -PO {round(self.dayTemp)}'
        subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        QApplication.quit()

    def onTrayActivated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open()

    def open(self):
        self.setIcon(self.lastTemp)
        self.resize(560, 720)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.activateWindow()
        self.raise_()
       
    def setIcon(self, temp, type:str = 'B'):
        print("Icon ->", temp)
        if type == 'B' or type == 'I':
            self.trayIcon.setIcon(QIcon(getIcon(temp, True)))

        # if self.isVisible():
        if type == 'B' or type == 'L':
            self.image.setPixmap(QPixmap(getIcon(temp)))

    def evaluate(self):
        xInfo = getWindowInfo()
        away = xInfo is None  # mouse left the screen (DeskFlow)
        info = xInfo

        effectOk = self.bridge.available()
        self.modeReason = ''
        if effectOk and self.forceGamma:
            self.modeReason = ' (forced)'
        elif effectOk and self.screenshotRunning():
            self.modeReason = ' (screenshot)'
        useKWin = effectOk and not self.modeReason
        if useKWin:
            kInfo = self.bridge.activeWindow()
            away = away or kInfo is None
            info = kInfo or xInfo

        self.setMode('kwin' if useKWin else 'gamma')
        self.modeLabel.setText("Mode: KWin compositor" if useKWin else f"Mode: gamma ramps{self.modeReason or ' (no compositor)'}")
        self.trackRecent(info)

        if useKWin:
            self.bridge.pushConfig(Config.dumps(self.entries))
            self.applyKWin(away)
        else:
            self.factor = 1.1 if away else Config.light_factor(self.entries, info or {})
            self.applyGamma()

    def setForceGamma(self, checked):
        self.forceGamma = bool(checked)
        for w in (self.forceBox, self.forceAction):
            if w.isChecked() != self.forceGamma:
                w.blockSignals(True)
                w.setChecked(self.forceGamma)
                w.blockSignals(False)

    @staticmethod
    def screenshotRunning() -> bool:
        return subprocess.run(['pgrep', '-x', 'spectacle'], stdout=subprocess.DEVNULL).returncode == 0

    def setMode(self, mode):
        if mode == self.mode:
            return
        print("Mode ->", mode)
        previous = self.mode
        self.mode = mode
        self.bridge.reset()

        if mode == 'kwin':
            # neutralise the gamma ramps, the effect does the work now
            subprocess.run(f'redshift -PO {round(self.dayTemp)}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        elif previous == 'kwin':
            self.bridge.pushNeutral()
            self.lastTemp = self.dayTemp

    def baseTemp(self):
        hr = 60 * 60
        sec = self.getTime()

        fadeInStart  = 18 * hr
        fadeInStop   = 22 * hr

        fadeOutStart = 8 * hr
        fadeOutStop  = 10 * hr

        if sec <= 14 * hr:
            temp = remap( fadeOutStart, fadeOutStop, self.nightTemp, self.dayTemp, sec )
        else:
            temp = remap( fadeInStart, fadeInStop, self.dayTemp, self.nightTemp, sec)
        return clamp( temp, self.nightTemp, self.dayTemp )

    def applyKWin(self, away):
        temp = self.baseTemp()
        idleT = clamp(inv_lerp(5, 20, getIdle() / 1000), 0.0, 1.0)
        self.bridge.pushState(temp, idleT, away)

        temp = round(temp)
        if temp != self.lastTemp:
            self.lastTemp = temp
            self.trayIcon.setToolTip(f"{temp}°K | X11 RedLamp (KWin)")
            self.setIcon(temp)

    def getTime(self):
        if '-t' in sys.argv:
            try:    self.timeTest += 5 * 60
            except: self.timeTest = 0
            return self.timeTest
        else:
            t = time.localtime()
            return t.tm_hour*60**2 + t.tm_min*60 + t.tm_sec

    def applyGamma(self):
        temp = self.baseTemp()

        temp = self.factorTemp(temp)



        # tempI = remap(30, 60, self.dayTemp , self.idleTemp, getIdle() / 1000)
        tempI = remap(5, 20, self.dayTemp , temp * 1.1, getIdle() / 1000)
        tempI = clamp( tempI, temp * 1.1, self.dayTemp )

        temp = round(min(temp, tempI))


        if self.lastTemp != temp:
            print(self.lastTemp, '->', temp)
            # self.trayIcon.setIcon(QIcon(getIcon(temp)))
            
            self.trayIcon.setToolTip(f"{round(temp)}°K | X11 RedLamp")
            self.setIcon(temp, 'I')

            
            try: 
                for t in range(round(self.lastTemp), round(temp), round((temp - self.lastTemp)/10)):                    
                    cmd = f'redshift -PO {round(t)}'
                    # print(cmd)
                    subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self.setIcon(t, 'L')
                    QApplication.processEvents()

            except: pass # Exception as e: print(e)

            cmd = f'redshift -PO {round(temp)}'
            # print(cmd)
            subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.setIcon(temp)
            


            self.lastTemp = round(temp)
            self.lastFac  = self.factor
            return True
        return False





if __name__ == "__main__":
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    man = LampManager()

    # Ctrl+C: the update timer keeps the interpreter awake so the handler runs
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sys.exit(app.exec())
