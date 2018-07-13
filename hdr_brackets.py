import sys
import os
import subprocess
import json
import exifread
from math import log
from PyQt4 import QtGui, QtCore
from concurrent.futures import ThreadPoolExecutor
from time import sleep
import http.client, urllib

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SCRIPT_DIR = SCRIPT_DIR+('/' if not SCRIPT_DIR.endswith('/') else '')

def read_json(fp):
    with open(fp, 'r') as f:
        data = json.load(f)
    return data

def get_exe_paths():
    global SCRIPT_DIR
    cf = os.path.join(SCRIPT_DIR, 'exe_paths.json')
    default_exe_paths = {
        "blender_exe": "",
        "luminance_cli_exe": ""
    }
    exe_paths = {}
    error = ""
    if not os.path.exists(cf):
        with open(cf, 'w') as f:
            f.write(json.dumps(default_exe_paths, f, indent=4, sort_keys=True))
        error = "You need to configure some paths first. Edit the 'exe_paths.json' file next to this script and fill in the paths."
    else:
        exe_paths = read_json(cf)
        for k in default_exe_paths.keys():
            if not os.path.exists(exe_paths[k]):
                error = exe_paths[k]+" either doesn't exist or is an invalid path."
    if error:
        print (error)
        input("Press enter to exit.")
        sys.exit(0)
    return exe_paths

EXE_PATHS = get_exe_paths()

def notify_phone(msg="Done"):
    pushover_cfg_f = os.path.join(SCRIPT_DIR, 'pushover.json')
    if not os.path.exists(pushover_cfg_f):
        return

    pushover_cfg = read_json(pushover_cfg_f)
    conn = http.client.HTTPSConnection("api.pushover.net:443")
    conn.request("POST", "/1/messages.json",
        urllib.parse.urlencode({
            "token": pushover_cfg['token'],
            "user": pushover_cfg['user'],
            "message": msg,
        }), { "Content-type": "application/x-www-form-urlencoded" })
    conn.getresponse()

def chunks(l, n):
    if n < 1:
        n = 1
    return [l[i:i + n] for i in range(0, len(l), n)]

def get_exif(filepath):
    f = open(filepath, 'rb')
    tags = exifread.process_file(f)
    f.close()
    resolution = str(tags["Image ImageWidth"]) + 'x' + str(tags["Image ImageLength"])
    shutter_speed = eval(str(tags["EXIF ExposureTime"]))
    aperture = eval(str(tags["EXIF FNumber"]))
    iso = int(str(tags["EXIF ISOSpeedRatings"]))
    return {"resolution": resolution, "shutter_speed": shutter_speed, "aperture": aperture, "iso": iso}

def ev_diff(bright_image, dark_image):
    dr_shutter = log(bright_image['shutter_speed']/dark_image['shutter_speed'], 2)
    dr_aperture = log(dark_image['aperture']/bright_image['aperture'], 1.41421)
    dr_iso = log(bright_image['iso']/dark_image['iso'], 2)
    return dr_shutter + dr_aperture + dr_iso

class HDRBrackets(QtGui.QMainWindow):
    
    def __init__(self):
        super(HDRBrackets, self).__init__()
        
        self.initUI()
        
    def initUI(self):
        clipboard = QtGui.QApplication.clipboard().text()

        pixmap = QtGui.QPixmap("icons/browse.png")
        icon_browse = QtGui.QIcon(pixmap)

        # ========== Input ==========
        initial_label = "Select a folder..."
        if clipboard:  # if a path is copied in clipboard, fill it in automatically
            if os.path.exists(clipboard):
                initial_label = clipboard

        lbl_input = QtGui.QLabel("Input Folder:", self)
        lbl_input.move(19,10)

        self.input_folder = QtGui.QLineEdit(initial_label, self)        
        self.input_folder.move(90,14)
        self.input_folder.resize(455, 21)
        self.input_folder.textChanged[str].connect(self.changeInputFolder)

        btn_browse = QtGui.QPushButton('', self)
        btn_browse.clicked.connect(self.set_input_folder)
        btn_browse.resize(21, 21)
        btn_browse.move(523, 14)        
        btn_browse.setFlat(True)
        btn_browse.setIcon(icon_browse)

        lbl_pattern = QtGui.QLabel("Matching Pattern:", self)
        lbl_pattern.move(19,41)

        self.extension = QtGui.QLineEdit(".tif", self)
        self.extension.setStyleSheet("qproperty-alignment: AlignRight;")
        self.extension.move(110,45)
        self.extension.resize(45, 21)

        self.num_threads = QtGui.QSpinBox(self)
        self.num_threads.resize(90, 22)
        self.num_threads.move(165, 45)
        self.num_threads.setRange(1, 9999999)
        self.num_threads.setSingleStep(1)
        self.num_threads.setPrefix("Threads: ")
        self.num_threads.setValue(6)

        lbl_pattern = QtGui.QLabel("Filters Used:", self)
        lbl_pattern.move(270,41)
        self.filter = QtGui.QComboBox(self)
        self.filter.addItem("None")
        self.filter.addItem("ND8")
        self.filter.addItem("ND400")
        self.filter.addItem("ND8 + ND400")
        self.filter.move(337, 45)
        self.filter.resize(90, 22)

        self.btn_execute = QtGui.QPushButton('Create HDRs', self)
        self.btn_execute.clicked.connect(self.execute)
        self.btn_execute.resize(self.btn_execute.sizeHint())
        self.btn_execute.move(472, 44)
        self.btn_execute.setEnabled(os.path.exists(self.input_folder.text()))

        self.progress = QtGui.QProgressBar(self)
        self.progress.setTextVisible(False)
        self.progress.move(3, 70)
        self.progress.resize(554, 8)
        self.progress.hide()

        
        # Window details
        self.setWindowTitle('HDR Brackets')
        self.setFixedSize(560, 80)
        self.setWindowIcon(QtGui.QIcon('icons/icon.png'))  
        self.center()
        self.show()

    def set_input_folder(self):
        path = str(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if path:  # if user didn't press cancel
            self.input_folder.setText(path)
            QtGui.QApplication.clipboard().setText(self.input_folder.text())  # copy path to clipboard

    def do_merge(self, blender_exe, merge_blend, merge_py, exifs, out_folder, filter_used, i, img_list, folder, luminance_cli_exe):
        print ("Merging", i)
        cmd = [
            blender_exe,
            '--background',
            merge_blend,
            '--factory-startup',
            '--python',
            merge_py,
            '--',
            exifs[0]['resolution'],
            out_folder,
            filter_used,
            str(i)
        ]
        cmd += img_list
        subprocess.call(cmd)

        f = 'merged_'+str(i).zfill(3)+'.exr'
        jpg_folder = folder+"Merged/jpg/"
        jpg_name = f.split('.')[0] + ".jpg"
        if not os.path.exists(jpg_folder):
            os.makedirs(jpg_folder)
        cmd = [
            luminance_cli_exe,
            '-l',
            out_folder + f,
            '-t',
            'reinhard02',
            '-q',
            '98',
            '-o',
            jpg_folder + jpg_name
        ]
        subprocess.call(cmd)

    def execute(self):
        print ("Starting...")
        self.progress.setValue(0)
        self.progress.show()

        global EXE_PATHS
        global SCRIPT_DIR
        blender_exe = EXE_PATHS['blender_exe']
        luminance_cli_exe = EXE_PATHS['luminance_cli_exe']
        merge_blend = os.path.join(SCRIPT_DIR, "blender", "HDR_Merge.blend")
        merge_py = os.path.join(SCRIPT_DIR, "blender", "blender_merge.py")

        folder = self.input_folder.text()
        folder = folder.replace('\\', '/')
        folder += '/' if not folder.endswith('/') else ''
        out_folder = folder + "Merged/exr/"
        files = [folder+f for f in os.listdir(folder) if f.endswith(self.extension.text())]

        # Analyze EXIF to determine number of brackets
        exifs = []
        for f in files:
            e = get_exif(f)
            if e in exifs:
                break
            exifs.append(e)
        brackets = len(exifs)
        print ("\nBrackets:", brackets)
        evs = [ev_diff({"shutter_speed": 1000000000, "aperture": 0.1, "iso": 1000000000000}, e) for e in exifs]
        evs = [ev-min(evs) for ev in evs]

        filter_used = self.filter.currentText().replace(' ', '').replace('+', '_')

        # Do merging
        executor = ThreadPoolExecutor(max_workers=self.num_threads.value())
        threads = []
        sets = chunks(files, brackets)
        print ("Sets:", len(sets), "\n")
        for i,s in enumerate(sets):
            img_list = []
            for ii,img in enumerate(s):
                img_list.append(img+'___'+str(evs[ii]))
            if not os.path.exists(os.path.join(out_folder, "merged_"+str(i).zfill(3)+".exr")):
                # self.do_merge (blender_exe, merge_blend, merge_py, exifs, out_folder, filter_used, i, img_list, folder, luminance_cli_exe)
                t = executor.submit(self.do_merge, blender_exe, merge_blend, merge_py, exifs, out_folder, filter_used, i, img_list, folder, luminance_cli_exe)
                threads.append(t)
            else:
                print ("Skipping set", i)

        while (any(t._state!="FINISHED" for t in threads)):
            sleep (2)
            QtCore.QCoreApplication.processEvents()
            num_finished = 0
            for tt in threads:
                if tt._state == "FINISHED":
                    num_finished += 1
            progress = (num_finished/len(threads))*100
            print ("Progress:", progress)
            self.progress.setValue(int(progress))

        print ("Done!!!")
        sf = "C:/Windows/Media/Speech On.wav"
        if os.path.exists(sf):
            QtGui.QSound(sf).play()
        notify_phone(folder)
        
    def center(self):        
        qr = self.frameGeometry()
        cp = QtGui.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def changeInputFolder(self, text):
        self.progress.hide()
        self.btn_execute.setEnabled(os.path.exists(self.input_folder.text()))
        
        
def main():
    print ("This window will report detailed progress of the blender renders.")
    print ("Use the other window to start the merging process.")
    
    app = QtGui.QApplication(sys.argv)
    ex = HDRBrackets()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()    
