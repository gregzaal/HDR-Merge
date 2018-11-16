import sys
import os
import subprocess
import json
import exifread
from math import log
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor
import threading
from time import sleep
import http.client, urllib

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)  # Built with cx_freeze
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SCRIPT_DIR = SCRIPT_DIR+('/' if not SCRIPT_DIR.endswith('/') else '')

def center(win):
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    y = (win.winfo_screenheight() // 2) - (height+32 // 2)  # Add 32 to account for titlebar & borders
    win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

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

def play_sound(sf):
    if os.path.exists(sf):
        try:
            from winsound import PlaySound, SND_FILENAME
        except ImportError:
            pass
        else:
            PlaySound(sf, SND_FILENAME)

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


class HDRBrackets(Frame):
    
    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master
        
        self.initUI()
        
    def initUI(self):
        self.master.title("HDR Brackets")
        self.pack(fill=BOTH, expand=True)

        padding = 8
        self.buttons_to_disable = []

        clipboard = None
        try:
            clipboard = Frame.clipboard_get(self)
        except TclError:
            pass

        # ========== Input ==========
        r1 = Frame(master=self)
        initial_label = "Select a folder..."
        if clipboard:  # if a path is copied in clipboard, fill it in automatically
            if os.path.exists(clipboard):
                initial_label = clipboard

        lbl_input = Label(r1, text="Input Folder:")
        lbl_input.pack(side=LEFT, padx=(padding, 0))

        self.input_folder = Entry(r1)
        self.input_folder.insert(0, initial_label)
        self.input_folder.pack(side=LEFT, fill=X, expand=True, padx=padding)
        self.buttons_to_disable.append(self.input_folder)

        btn_browse = Button(r1, text='Browse', command=self.set_input_folder)
        btn_browse.pack(side=RIGHT, padx=(0, padding))
        self.buttons_to_disable.append(btn_browse)

        r1.pack(fill=X, pady=(padding, 0))
        r2 = Frame(master=self)

        lbl_pattern = Label(r2, text="Matching Pattern:")
        lbl_pattern.pack(side=LEFT, padx=(padding, 0))
        self.extension = Entry(r2, width=6)
        self.extension.insert(0, ".tif")
        self.extension.pack(side=LEFT, padx=(padding/2, 0))
        self.buttons_to_disable.append(self.extension)

        lbl_threads = Label(r2, text="Threads:")
        lbl_threads.pack(side=LEFT, padx=(padding, 0))
        self.num_threads = Spinbox(r2, from_=1, to=9999999, width=2)
        self.num_threads.delete(0, "end")
        self.num_threads.insert(0, "6")
        self.num_threads.pack(side=LEFT, padx=(padding/3, 0))
        self.buttons_to_disable.append(self.num_threads)

        self.btn_execute = Button(r2, text='Create HDRs', command=self.execute)
        self.btn_execute.pack(side=RIGHT, fill=X, expand=True, padx=padding)
        self.buttons_to_disable.append(self.btn_execute)

        r2.pack(fill=X, pady=(padding, 0))
        r3 = Frame(master=self)

        self.progress=ttk.Progressbar(r3,orient=HORIZONTAL,length=100,mode='determinate')
        self.progress.pack(fill=X)

        r3.pack(fill=X, pady=(padding, 0))


    def set_input_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.input_folder.delete(0, END)
            self.input_folder.insert(0, path)
            self.btn_execute['text'] = "Create HDRs"
            self.btn_execute['command'] = self.execute
            self.progress['value'] = 0


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
        def real_execute():
            if not os.path.exists(self.input_folder.get()):
                messagebox.showerror("Folder does not exist", "The input path you have selected does not exist!")
                return

            print ("Starting...")
            self.btn_execute['text'] = "Busy..."
            self.progress['value'] = 0

            for btn in self.buttons_to_disable:
                btn['state'] = 'disabled'

            global EXE_PATHS
            global SCRIPT_DIR
            blender_exe = EXE_PATHS['blender_exe']
            luminance_cli_exe = EXE_PATHS['luminance_cli_exe']
            merge_blend = os.path.join(SCRIPT_DIR, "blender", "HDR_Merge.blend")
            merge_py = os.path.join(SCRIPT_DIR, "blender", "blender_merge.py")

            folder = self.input_folder.get()
            folder = folder.replace('\\', '/')
            folder += '/' if not folder.endswith('/') else ''
            out_folder = folder + "Merged/exr/"
            files = [folder+f for f in os.listdir(folder) if f.endswith(self.extension.get())]

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

            filter_used = "None"  # self.filter.get().replace(' ', '').replace('+', '_')  # Depreciated

            # Do merging
            executor = ThreadPoolExecutor(max_workers=int(self.num_threads.get()))
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
                self.update()
                num_finished = 0
                for tt in threads:
                    if tt._state == "FINISHED":
                        num_finished += 1
                progress = (num_finished/len(threads))*100
                print ("Progress:", progress)
                self.progress['value'] = int(progress)

            print ("Done!!!")
            notify_phone(folder)
            for btn in self.buttons_to_disable:
                btn['state'] = 'normal'
            self.btn_execute['text'] = "Done!"
            self.btn_execute['command'] = self.quit
            play_sound("C:/Windows/Media/Speech On.wav")
            self.update()

        threading.Thread(target=real_execute).start()  # Run in a separate thread to keep UI alive


    def quit(self):
        global root
        root.destroy()
        
        
def main():
    print ("This window will report detailed progress of the blender renders.")
    print ("Use the other window to start the merging process.")
    
    global root
    root = Tk()
    root.geometry("450x86")
    center(root)
    root.iconbitmap(os.path.join(SCRIPT_DIR, "icons/icon.ico"))
    app = HDRBrackets(root)
    root.mainloop()


if __name__ == '__main__':
    main()    
