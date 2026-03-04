import sys
import os
import json
import subprocess
import socket
from pathlib import Path
from PyQt6.QtWidgets import (
	QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
	QLineEdit, QPushButton, QFileDialog, QListWidget, QTabWidget,
	QSpinBox, QComboBox, QTextEdit, QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt

CONFIG_PATH = os.path.join(Path.home(), ".gzdoom_launcher_config.json")

KNOWN_IWADS = {
	"doom.wad","doom2.wad","plutonia.wad","tnt.wad",
	"freedoom1.wad","freedoom2.wad",
	"heretic.wad","hexen.wad","strife1.wad",
	"doom1.wad","ultimate.wad","chex.wad","chex2.wad"
}

ENGINE_NAMES = [
    "gzdoom.exe",
    "uzdoom.exe",
    "zdoom.exe",
    "lzdoom.exe"
]

COMMON_ENGINE_PATHS = [
    os.getcwd(),
    r"C:\Program Files\GZDoom",
    r"C:\Program Files (x86)\GZDoom",
    r"C:\Program Files\UZDoom",
    r"C:\Program Files (x86)\UZDoom",
    os.path.join(os.getenv("APPDATA",""),"GZDoom"),
    os.path.join(os.getenv("APPDATA",""),"UZDoom"),
]

DEFAULT_MAP = ""

# ---------------- Config ----------------

def load_config():
	try:
		if os.path.isfile(CONFIG_PATH):
			with open(CONFIG_PATH,"r",encoding="utf-8") as f:
				return json.load(f)
	except:
		pass
	return {}

def save_config(cfg):
	try:
		with open(CONFIG_PATH,"w",encoding="utf-8") as f:
			json.dump(cfg,f,indent=2)
	except:
		pass

def find_engine():
    for base in [os.getcwd()] + COMMON_ENGINE_PATHS:
        if not base:
            continue
        for name in ENGINE_NAMES:
            exe = os.path.join(base, name)
            if os.path.isfile(exe):
                return os.path.abspath(exe)
    return None

def scan_iwads(dirs):
	found=[]
	for d in dirs:
		if not d:
			continue
		try:
			if os.path.isdir(d):
				for f in os.listdir(d):
					if f.lower() in KNOWN_IWADS:
						full = os.path.join(d,f)
						if os.path.isfile(full) and full not in found:
							found.append(os.path.abspath(full))
		except:
			continue
	return sorted(found,key=lambda x: os.path.basename(x).lower())

# ---------------- Launcher ----------------

class MultiplayerDoomLauncher(QWidget):

	def __init__(self):
		super().__init__()

		self.setWindowTitle("(Previously GZDoom) Multiplayer Launcher")
		self.setGeometry(180,120,900,600)

		self.config = load_config()
		self.engine_path = self.config.get("engine_path")

		self.ensure_engine()
		self.detected_iwads = self.detect_iwads()

		main_layout = QVBoxLayout()

		# ---------------- Top Bar ----------------

		self.status_label = QLabel()
		self.update_status_label()

		btn_change = QPushButton("Change engine...")
		btn_change.clicked.connect(self.change_engine)

		top_layout = QHBoxLayout()
		top_layout.addWidget(self.status_label)
		top_layout.addStretch(1)
		top_layout.addWidget(btn_change)

		main_layout.addLayout(top_layout)

		# ---------------- Global IWAD ----------------

		iwad_layout = QHBoxLayout()

		self.iwad_combo = QComboBox()
		self.iwad_combo.addItem("Select detected IWAD...")

		self.iwad_path = QLineEdit()
		self.iwad_path.setPlaceholderText("Or browse for an IWAD")

		btn_browse_iwad = QPushButton("Browse IWAD...")
		btn_browse_iwad.clicked.connect(
			lambda: self.pick_iwad(self.iwad_combo, self.iwad_path)
		)

		iwad_layout.addWidget(QLabel("IWAD:"))
		iwad_layout.addWidget(self.iwad_combo,3)
		iwad_layout.addWidget(self.iwad_path,3)
		iwad_layout.addWidget(btn_browse_iwad)

		main_layout.addLayout(iwad_layout)

		# ---------------- Global PWAD (Drag & Drop Enabled) ----------------

		pwad_layout = QVBoxLayout()

		self.pwad_list = QListWidget()
		self.pwad_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
		self.pwad_list.setAcceptDrops(True)
		self.pwad_list.setDragEnabled(True)

		pwad_btns = QHBoxLayout()

		btn_add = QPushButton("Add Mod")
		btn_add.clicked.connect(lambda: self.add_pwads())

		btn_rem = QPushButton("Remove Selected")
		btn_rem.clicked.connect(lambda: self.remove_selected())

		pwad_btns.addWidget(btn_add)
		pwad_btns.addWidget(btn_rem)

		pwad_layout.addWidget(QLabel("PWADs / PK3s"))
		pwad_layout.addWidget(self.pwad_list)
		pwad_layout.addLayout(pwad_btns)

		main_layout.addLayout(pwad_layout)

		# Enable window-level drag & drop
		self.setAcceptDrops(True)

		# ---------------- Tabs ----------------

		self.tabs = QTabWidget()

		self.host_tab = QWidget()
		self.join_tab = QWidget()

		self.tabs.addTab(self.host_tab,"Host Game")
		self.tabs.addTab(self.join_tab,"Join Game")

		main_layout.addWidget(self.tabs)

		# ---------------- Console ----------------

		self.console = QTextEdit()
		self.console.setReadOnly(True)

		main_layout.addWidget(QLabel("Command Preview:"))
		main_layout.addWidget(self.console)

		self.setLayout(main_layout)

		self.init_host_tab()
		self.init_join_tab()

		self.refresh_iwads()
		self.load_config_values()

	# ---------------- Drag & Drop ----------------

	def dragEnterEvent(self, event):
		if event.mimeData().hasUrls():
			event.acceptProposedAction()

	def dropEvent(self, event):
		for url in event.mimeData().urls():
			path = url.toLocalFile()
			if os.path.isfile(path):
				ext = os.path.splitext(path)[1].lower()
				if ext in [".wad",".pk3",".pk7"]:
					self.add_pwad_to_list(path)

	# ---------------- Helpers ----------------

	def add_pwad_to_list(self, path):
		path = os.path.abspath(path)
		if not any(self.pwad_list.item(i).text()==path
				   for i in range(self.pwad_list.count())):
			self.pwad_list.addItem(path)

	def ensure_engine(self):
		if self.engine_path and os.path.isfile(self.engine_path):
			return
		found = find_engine()
		if found:
			self.engine_path = found

	def update_status_label(self):
		if self.engine_path and os.path.isfile(self.engine_path):
			self.status_label.setText(f" Using engine: {self.engine_path}")
		else:
			self.status_label.setText("Doom Port (Engine e.g. GZDoom, UZDoom) executable not set")

	def change_engine(self):
		file,_ = QFileDialog.getOpenFileName(
			self,"Select engine","","Executable (*.exe)"
		)
		if file:
			self.engine_path = os.path.abspath(file)
			self.save_config()
			self.update_status_label()

	def detect_iwads(self):
		dirs = list(COMMON_ENGINE_PATHS)
		if self.engine_path:
			dirs.append(os.path.dirname(self.engine_path))
		dirs.append(os.getcwd())
		return scan_iwads(dirs)

	def refresh_iwads(self):
		self.detected_iwads = self.detect_iwads()
		self.iwad_combo.clear()
		self.iwad_combo.addItem("Select detected IWAD...")
		for iwad in self.detected_iwads:
			self.iwad_combo.addItem(iwad)

	def pick_iwad(self,combo,lineedit):
		file,_ = QFileDialog.getOpenFileName(
			self,"Select IWAD","","WAD Files (*.wad)"
		)
		if file:
			absf = os.path.abspath(file)
			combo.addItem(absf)
			combo.setCurrentText(absf)
			lineedit.setText(absf)

	def get_iwad(self):
		if self.iwad_combo.currentIndex()>0:
			return self.iwad_combo.currentText()
		text = self.iwad_path.text().strip()
		return text if text else None

	def add_pwads(self):
		files,_ = QFileDialog.getOpenFileNames(
			self,"Select Mods","","WAD/PK3 Files (*.wad *.pk3 *.pk7)"
		)
		for f in files:
			self.add_pwad_to_list(f)

	def remove_selected(self):
		for item in self.pwad_list.selectedItems():
			self.pwad_list.takeItem(self.pwad_list.row(item))

	# ---------------- Command ----------------

	def build_command(self, exe, iwad, pwads, extra_args="", warp=None, skill=None, host=None, join=None):

		args = ["-iwad", iwad]

		for p in pwads:
			args += ["-file", p]

		# Only include warp + skill if warp exists
		if warp:
			args += ["-warp", warp]
			if skill:
				args += ["-skill", str(skill)]

		if host:
			args += ["-host", str(host)]

		if join:
			args += ["-join", join]

		if extra_args:
			args += extra_args.split()

		cmd = [exe] + args
		self.console.setPlainText(" ".join(cmd))
		return cmd

	def launch_game(self, **kwargs):
		cmd = self.build_command(**kwargs)
		try:
			subprocess.Popen(cmd)
		except Exception as e:
			QMessageBox.critical(self,"Launch Failed",str(e))

	# ---------------- Host ----------------

	def init_host_tab(self):
		layout = QVBoxLayout()

		map_layout = QHBoxLayout()

		self.map_name = QLineEdit()
		self.map_name.setPlaceholderText("Leave empty for title screen")

		self.player_count = QSpinBox()
		self.player_count.setRange(2,8)
		self.player_count.setValue(2)

		self.skill = QComboBox()
		self.skill.addItems([
			"1 - I'm too young to die",
			"2 - Hey, not too rough",
			"3 - Hurt me plenty",
			"4 - Ultra-Violence",
			"5 - Nightmare!"
		])

		map_layout.addWidget(QLabel("Map:"))
		map_layout.addWidget(self.map_name)
		map_layout.addWidget(QLabel("Players:"))
		map_layout.addWidget(self.player_count)
		map_layout.addWidget(QLabel("Skill:"))
		map_layout.addWidget(self.skill)

		layout.addLayout(map_layout)

		self.extra_args = QLineEdit()
		self.extra_args.setPlaceholderText("Extra launch options")

		layout.addWidget(self.extra_args)

		btn_host = QPushButton("Host Game")
		btn_host.clicked.connect(self.host_game)

		btn_single = QPushButton("Play Single Player")
		btn_single.clicked.connect(self.play_single)

		layout.addWidget(btn_host)
		layout.addWidget(btn_single)

		local_hostname = socket.gethostname() #get IP
		ip_addresses = socket.gethostbyname_ex(local_hostname)[2]
		filtered_ips = [ip for ip in ip_addresses if not ip.startswith("127.")]
		first_ip = filtered_ips[:1]
		layout.addWidget(QLabel("IP Address: "+first_ip[0])) # add IP te t

		self.host_tab.setLayout(layout)

	def host_game(self):
		iwad = self.get_iwad()
		if not iwad:
			QMessageBox.warning(self,"Missing IWAD","Select an IWAD.")
			return

		pwads = [self.pwad_list.item(i).text()
				for i in range(self.pwad_list.count())]

		self.launch_game(
			exe=self.engine_path,
			iwad=iwad,
			pwads=pwads,
			warp=self.map_name.text().strip() or None,
			skill=self.skill.currentIndex()+1,
			host=self.player_count.value(),
			extra_args=self.extra_args.text().strip()
		)

	def play_single(self):
		iwad = self.get_iwad()
		if not iwad:
			QMessageBox.warning(self,"Missing IWAD","Select an IWAD.")
			return

		pwads = [self.pwad_list.item(i).text()
				 for i in range(self.pwad_list.count())]

		self.launch_game(
			exe=self.engine_path,
			iwad=iwad,
			pwads=pwads,
			warp=self.map_name.text().strip() or None,
			skill=self.skill.currentIndex()+1,
			extra_args=self.extra_args.text().strip()
		)

	# ---------------- Join ----------------

	def init_join_tab(self):
		layout = QVBoxLayout()

		ip_layout = QHBoxLayout()

		self.ip_address = QLineEdit()
		self.ip_address.setPlaceholderText("Host IP")

		ip_layout.addWidget(QLabel("Host IP:"))
		ip_layout.addWidget(self.ip_address)

		layout.addLayout(ip_layout)

		self.join_extra_args = QLineEdit()
		self.join_extra_args.setPlaceholderText("Extra launch options")

		layout.addWidget(self.join_extra_args)

		btn_join = QPushButton("Join Game")
		btn_join.clicked.connect(self.join_game)

		layout.addWidget(btn_join)

		self.join_tab.setLayout(layout)

	def join_game(self):
		ip = self.ip_address.text().strip()
		iwad = self.get_iwad()

		if not ip or not iwad:
			QMessageBox.warning(self,"Missing Info",
								"IP and IWAD required.")
			return

		pwads = [self.pwad_list.item(i).text()
				 for i in range(self.pwad_list.count())]

		self.launch_game(
			exe=self.engine_path,
			iwad=iwad,
			pwads=pwads,
			join=ip,
			extra_args=self.join_extra_args.text().strip()
		)

	# ---------------- Config ----------------

	def save_config(self):
		cfg = {
			"engine_path": self.engine_path,
			"iwad": self.get_iwad(),
			"pwads": [self.pwad_list.item(i).text()
					  for i in range(self.pwad_list.count())],
			"map": self.map_name.text(),
			"players": self.player_count.value(),
			"skill": self.skill.currentIndex(),
			"extra": self.extra_args.text(),
			"join_ip": self.ip_address.text(),
			"join_extra": self.join_extra_args.text()
		}
		save_config(cfg)

	def load_config_values(self):
		cfg = load_config()

		if cfg.get("iwad"):
			self.iwad_combo.addItem(cfg["iwad"])
			self.iwad_combo.setCurrentText(cfg["iwad"])

		for p in cfg.get("pwads",[]):
			self.add_pwad_to_list(p)

		self.map_name.setText(cfg.get("map",""))
		self.player_count.setValue(cfg.get("players",2))
		self.skill.setCurrentIndex(cfg.get("skill",2))
		self.extra_args.setText(cfg.get("extra",""))
		self.ip_address.setText(cfg.get("join_ip",""))
		self.join_extra_args.setText(cfg.get("join_extra",""))

	def closeEvent(self,event):
		self.save_config()
		event.accept()

# ---------------- Main ----------------

if __name__=="__main__":
	app = QApplication(sys.argv)
	win = MultiplayerDoomLauncher()
	win.show()
	sys.exit(app.exec())