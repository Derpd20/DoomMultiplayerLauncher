import sys
import os
import json
import subprocess
import socket
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFileDialog, QListWidget, QTabWidget,
                             QSpinBox, QComboBox, QTextEdit, QMessageBox, QAbstractItemView)
from PyQt6.QtCore import Qt

CONFIG_PATH = os.path.join(Path.home(), ".gzdoom_launcher_config.json")
KNOWN_IWADS = {"doom.wad","doom2.wad","plutonia.wad","tnt.wad",
                "freedoom1.wad","freedoom2.wad",
                "heretic.wad","hexen.wad","strife1.wad",
                "doom1.wad","ultimate.wad","chex.wad","chex2.wad"}

COMMON_GZDOOM_PATHS = [
    os.getcwd(),
    r"C:\Program Files\GZDoom",
    r"C:\Program Files (x86)\GZDoom",
    os.path.join(os.getenv("APPDATA",""),"GZDoom"),
    r"C:\Program Files (x86)\Steam\steamapps\common\Doom 2\base",
    r"C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\base",
    r"C:\Program Files\Steam\steamapps\common\Doom 2\base",
    r"C:\Program Files\Steam\steamapps\common\Ultimate Doom\base"
]

DEFAULT_MAP = "01"

def load_config():
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH,"r",encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH,"w",encoding="utf-8") as f:
            json.dump(cfg,f,indent=2)
    except: pass

def find_gzdoom():
    for base in [os.getcwd()]+COMMON_GZDOOM_PATHS:
        if base:
            exe = os.path.join(base,"gzdoom.exe")
            if os.path.isfile(exe): return os.path.abspath(exe)
    return None

def scan_iwads(dirs):
    found=[]
    for d in dirs:
        if not d: continue
        try:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower() in KNOWN_IWADS:
                        full = os.path.join(d,f)
                        if os.path.isfile(full) and full not in found:
                            found.append(os.path.abspath(full))
        except: continue
    return sorted(found,key=lambda x: os.path.basename(x).lower())

class GZDoomLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GZDoom Multiplayer Launcher")
        self.setGeometry(180,120,820,560)
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #eee; font: 10pt "Segoe UI"; }
            QPushButton { padding: 6px; }
            QLineEdit, QComboBox, QListWidget, QTextEdit { background-color: #121212; color: #fff; }
            QLabel { padding: 2px; }
        """)
        self.config = load_config()
        self.gzdoom_path = self.config.get("gzdoom_path")
        self.ensure_gzdoom()
        self.detected_iwads = self.detect_iwads()

        self.tabs = QTabWidget()
        self.host_tab = QWidget()
        self.join_tab = QWidget()
        self.tabs.addTab(self.host_tab,"Host Game")
        self.tabs.addTab(self.join_tab,"Join Game")
        self.tabs.currentChanged.connect(self.highlight_tab)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color:#0b0b0b;color:#7CFC00;font-family:Consolas;")

        self.status_label = QLabel()
        self.update_status_label()
        btn_change = QPushButton("Change gzdoom.exe...")
        btn_change.clicked.connect(self.change_gzdoom)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.status_label)
        top_layout.addStretch(1)
        top_layout.addWidget(btn_change)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(QLabel("Command Preview:"))
        main_layout.addWidget(self.console)
        self.setLayout(main_layout)

        self.init_host_tab()
        self.init_join_tab()
        self.refresh_iwads()
        self.load_config_values()
        self.highlight_tab(self.tabs.currentIndex())

    # --- UI helpers ---
    def highlight_tab(self,index):
        for i in range(self.tabs.count()):
            self.tabs.tabBar().setTabTextColor(i,Qt.GlobalColor.yellow if i==index else Qt.GlobalColor.white)

    def ensure_gzdoom(self):
        if self.gzdoom_path and os.path.isfile(self.gzdoom_path): return
        found = find_gzdoom()
        if found: self.gzdoom_path=found
        else:
            dlg = QFileDialog(self,"Locate gzdoom.exe")
            dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
            dlg.setNameFilter("Executable (gzdoom.exe)")
            if dlg.exec():
                files = dlg.selectedFiles()
                if files and os.path.isfile(files[0]):
                    self.gzdoom_path = files[0]
                    return
            QMessageBox.warning(self,"gzdoom.exe not found",
                                "Couldn't find gzdoom.exe automatically. Use 'Change gzdoom.exe...'")

    def refresh_iwads(self):
        self.detected_iwads = self.detect_iwads()
        for combo in [self.iwad_combo, self.join_iwad_combo]:
            placeholder = combo.itemText(0)
            combo.clear()
            combo.addItem(placeholder)
            for iwad in self.detected_iwads:
                combo.addItem(iwad)

    def change_gzdoom(self):
        file,_ = QFileDialog.getOpenFileName(self,"Select gzdoom.exe","","Executable (gzdoom.exe);;All Files (*)")
        if file: self.gzdoom_path=os.path.abspath(file); self.save_config(); self.refresh_iwads(); self.update_status_label()

    def update_status_label(self):
        if self.gzdoom_path and os.path.isfile(self.gzdoom_path):
            self.status_label.setText(f"Using gzdoom: {self.gzdoom_path}")
        else:
            self.status_label.setText("gzdoom.exe: not set")

    def detect_iwads(self):
        dirs = list(COMMON_GZDOOM_PATHS)
        if self.gzdoom_path:
            dirs.append(os.path.dirname(self.gzdoom_path))
        dirs.append(os.getcwd())
        appdata = os.path.join(os.getenv("APPDATA",""),"gzdoom")
        dirs.append(appdata)
        return scan_iwads(dirs)

    def pick_iwad(self,combo,lineedit):
        file,_=QFileDialog.getOpenFileName(self,"Select IWAD","","WAD Files (*.wad);;All Files (*)")
        if file:
            absf=os.path.abspath(file)
            self.add_to_combo(combo,absf)
            lineedit.setText(absf)

    def add_to_combo(self,combo,text):
        if not any(combo.itemText(i)==text for i in range(combo.count())):
            combo.addItem(text)
        combo.setCurrentIndex(next((i for i in range(combo.count()) if combo.itemText(i)==text),0))

    def add_pwads(self,listwidget):
        files,_=QFileDialog.getOpenFileNames(self,"Select PWADs/PK3s","","WAD/PK3 Files (*.wad *.pk3 *.pk7);;All Files (*)")
        for f in files:
            f=os.path.abspath(f)
            if not any(listwidget.item(i).text()==f for i in range(listwidget.count())):
                listwidget.addItem(f)

    def remove_selected(self,listwidget):
        for item in listwidget.selectedItems():
            listwidget.takeItem(listwidget.row(item))

    def get_iwad(self,combo,lineedit):
        if combo.currentIndex()>0: return combo.currentText()
        text=lineedit.text().strip()
        return text if text else None

    def quote_path(self, p):
        p = p.strip('"')
        return f'"{p}"'

    # --- Command builder ---
    def build_command(self, exe, iwad, pwads, extra_args=[], warp=None, skill=None, host=None, join=None):
        args = ["-iwad", iwad]
        for p in pwads:
            args += ["-file", p]
        if warp: args += ["-warp", warp]
        if skill: args += ["-skill", str(skill)]
        if host: args += ["-host", str(host)]
        if join: args += ["-join", join]
        if extra_args: args += extra_args.split()
        cmd = [exe] + args
        self.console.setPlainText(" ".join(cmd))
        return cmd

    def launch_game(self,exe,iwad,pwads,extra_args=[],warp=None,skill=None,host=None,join=None):
        cmd = self.build_command(exe,iwad,pwads,extra_args,warp,skill,host,join)
        print(str(cmd))
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            QMessageBox.critical(self,"Failed to launch",f"Error:\n{e}")

    # --- Unified game launchers ---
    def launch_host_or_single(self, single=False):
        iwad = self.get_iwad(self.iwad_combo, self.iwad_path)
        if not iwad or not (self.gzdoom_path and os.path.isfile(self.gzdoom_path)):
            QMessageBox.warning(self, "Missing files", "Please select IWAD and ensure gzdoom.exe exists.")
            return
        pwads = [self.pwad_list.item(i).text() for i in range(self.pwad_list.count())]
        warp_text = self.map_name.text().strip()
        warp = warp_text if warp_text else None  # Only include -warp if not empty
        skill_text = self.skill.currentIndex() + 1
        skill = skill_text if warp_text else None  # Only include -skill if -warp not empty
        host = None if single else self.player_count.value()
        self.launch_game(self.gzdoom_path, iwad, pwads, extra_args=self.extra_args.text().strip(),
                        warp=warp, skill=skill, host=host)

    def launch_join(self):
        ip = self.ip_address.text().strip()
        iwad = self.get_iwad(self.join_iwad_combo, self.join_iwad_path)
        if not ip or not iwad or not (self.gzdoom_path and os.path.isfile(self.gzdoom_path)):
            QMessageBox.warning(self, "Missing information", "Please ensure IP, IWAD, and gzdoom.exe are set.")
            return
        pwads = [self.join_pwad_list.item(i).text() for i in range(self.join_pwad_list.count())]
        self.launch_game(self.gzdoom_path, iwad, pwads, extra_args=self.join_extra_args.text().strip(), join=ip)

    # --- Connect buttons ---
    def host_game(self): self.launch_host_or_single(single=False)
    def test_single(self): self.launch_host_or_single(single=True)
    def join_game(self): self.launch_join()

    # --- Tab inits ---
    def init_host_tab(self):
        layout=QVBoxLayout()
        # IWAD
        iwad_layout=QHBoxLayout()
        self.iwad_combo=QComboBox(); self.iwad_combo.addItem("Select detected IWAD...")
        self.iwad_path=QLineEdit(); self.iwad_path.setPlaceholderText("Or browse for an IWAD")
        btn_browse=QPushButton("Browse IWAD..."); btn_browse.clicked.connect(lambda: self.pick_iwad(self.iwad_combo,self.iwad_path))
        iwad_layout.addWidget(QLabel("IWAD:")); iwad_layout.addWidget(self.iwad_combo,3); iwad_layout.addWidget(self.iwad_path,3); iwad_layout.addWidget(btn_browse)
        layout.addLayout(iwad_layout)
        # PWADs
        pwad_layout=QVBoxLayout()
        self.pwad_list=QListWidget()
        self.pwad_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        pwad_btns=QHBoxLayout()
        btn_add=QPushButton("Add Mod"); btn_add.clicked.connect(lambda: self.add_pwads(self.pwad_list))
        btn_rem=QPushButton("Remove Selected"); btn_rem.clicked.connect(lambda: self.remove_selected(self.pwad_list))
        pwad_btns.addWidget(btn_add); pwad_btns.addWidget(btn_rem)
        pwad_layout.addWidget(QLabel("PWADs / PK3s:")); pwad_layout.addWidget(self.pwad_list); pwad_layout.addLayout(pwad_btns)
        layout.addLayout(pwad_layout)
        # Map/players/skill
        map_layout=QHBoxLayout()
        self.map_name=QLineEdit("Leave empty to start on title screen")
        self.player_count=QSpinBox(); self.player_count.setRange(2,8); self.player_count.setValue(2)
        self.skill=QComboBox(); self.skill.addItems(["1 - I'm too young to die","2 - Hey, not too rough",
                                                    "3 - Hurt me plenty","4 - Ultra-Violence","5 - Nightmare!"])
        map_layout.addWidget(QLabel("Map:")); map_layout.addWidget(self.map_name)
        map_layout.addWidget(QLabel("Players:")); map_layout.addWidget(self.player_count)
        map_layout.addWidget(QLabel("Skill:")); map_layout.addWidget(self.skill)
        layout.addLayout(map_layout)
        # Extra args
        self.extra_args=QLineEdit(); self.extra_args.setPlaceholderText("Extra launch options")
        layout.addWidget(self.extra_args)
        # Buttons
        btn_host=QPushButton("Host Game"); btn_host.clicked.connect(self.host_game)
        btn_single=QPushButton("Play Single Player"); btn_single.clicked.connect(self.test_single)
        local_hostname = socket.gethostname() #get IP
        ip_addresses = socket.gethostbyname_ex(local_hostname)[2]
        filtered_ips = [ip for ip in ip_addresses if not ip.startswith("127.")]
        first_ip = filtered_ips[:1]
        layout.addWidget(QLabel("IP Address: "+first_ip[0]))
        layout.addWidget(btn_host)
        layout.addWidget(btn_single)
        self.host_tab.setLayout(layout)

    def init_join_tab(self):
        layout=QVBoxLayout()
        ip_layout=QHBoxLayout()
        self.ip_address=QLineEdit(); self.ip_address.setPlaceholderText("Host IP")
        ip_layout.addWidget(QLabel("Host IP:")); ip_layout.addWidget(self.ip_address)
        layout.addLayout(ip_layout)
        # IWAD
        iwad_layout=QHBoxLayout()
        self.join_iwad_combo=QComboBox(); self.join_iwad_combo.addItem("Select detected IWAD...")
        self.join_iwad_path=QLineEdit(); self.join_iwad_path.setPlaceholderText("Or browse for an IWAD")
        btn_browse=QPushButton("Browse IWAD..."); btn_browse.clicked.connect(lambda: self.pick_iwad(self.join_iwad_combo,self.join_iwad_path))
        iwad_layout.addWidget(QLabel("IWAD:")); iwad_layout.addWidget(self.join_iwad_combo,3); iwad_layout.addWidget(self.join_iwad_path,3); iwad_layout.addWidget(btn_browse)
        layout.addLayout(iwad_layout)
        # PWADs
        pwad_layout=QVBoxLayout()
        self.join_pwad_list=QListWidget()
        self.join_pwad_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        pwad_btns=QHBoxLayout()
        btn_add=QPushButton("Add Mod"); btn_add.clicked.connect(lambda: self.add_pwads(self.join_pwad_list))
        btn_rem=QPushButton("Remove Selected"); btn_rem.clicked.connect(lambda: self.remove_selected(self.join_pwad_list))
        pwad_btns.addWidget(btn_add); pwad_btns.addWidget(btn_rem)
        pwad_layout.addWidget(QLabel("PWADs / PK3s:")); pwad_layout.addWidget(self.join_pwad_list); pwad_layout.addLayout(pwad_btns)
        layout.addLayout(pwad_layout)
        # Extra args
        self.join_extra_args=QLineEdit(); self.join_extra_args.setPlaceholderText("Extra launch options")
        layout.addWidget(self.join_extra_args)
        # Join button
        btn_join=QPushButton("Join Game"); btn_join.clicked.connect(self.join_game)
        layout.addWidget(btn_join)
        self.join_tab.setLayout(layout)

    # --- Config save/load ---
    def save_config(self):
        cfg={
            "gzdoom_path":self.gzdoom_path,
            "host_iwad":self.get_iwad(self.iwad_combo,self.iwad_path),
            "host_pwads":[self.pwad_list.item(i).text() for i in range(self.pwad_list.count())],
            "host_map":self.map_name.text(),
            "host_players":self.player_count.value(),
            "host_skill":self.skill.currentIndex(),
            "host_extra_args":self.extra_args.text(),
            "join_iwad":self.get_iwad(self.join_iwad_combo,self.join_iwad_path),
            "join_pwads":[self.join_pwad_list.item(i).text() for i in range(self.join_pwad_list.count())],
            "join_ip":self.ip_address.text(),
            "join_extra_args":self.join_extra_args.text()
        }
        save_config(cfg)

    def load_config_values(self):
        cfg=load_config()
        host_iwad=cfg.get("host_iwad"); host_pwads=cfg.get("host_pwads",[])
        if host_iwad: self.add_to_combo(self.iwad_combo,host_iwad)
        for p in host_pwads:
            if not any(self.pwad_list.item(i).text()==p for i in range(self.pwad_list.count())):
                self.pwad_list.addItem(p)
        self.map_name.setText(cfg.get("host_map",DEFAULT_MAP))
        self.player_count.setValue(cfg.get("host_players",2))
        self.skill.setCurrentIndex(cfg.get("host_skill",2))
        self.extra_args.setText(cfg.get("host_extra_args",""))

        join_iwad=cfg.get("join_iwad"); join_pwads=cfg.get("join_pwads",[])
        if join_iwad: self.add_to_combo(self.join_iwad_combo,join_iwad)
        for p in join_pwads:
            if not any(self.join_pwad_list.item(i).text()==p for i in range(self.join_pwad_list.count())):
                self.join_pwad_list.addItem(p)
        self.ip_address.setText(cfg.get("join_ip",""))
        self.join_extra_args.setText(cfg.get("join_extra_args",""))

    def closeEvent(self,event):
        self.save_config(); event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv)
    win=GZDoomLauncher()
    win.show()
    sys.exit(app.exec())