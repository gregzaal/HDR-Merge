import os
from cx_Freeze import setup, Executable

PYTHON_INSTALL_DIR = os.path.dirname(os.path.dirname(os.__file__))
os.environ['TCL_LIBRARY'] = os.path.join(PYTHON_INSTALL_DIR, 'tcl', 'tcl8.6')
os.environ['TK_LIBRARY'] = os.path.join(PYTHON_INSTALL_DIR, 'tcl', 'tk8.6')

options = {
    'build_exe': {
        'include_files':[
            os.path.join('blender/'),
            os.path.join('icons/'),
            os.path.join(PYTHON_INSTALL_DIR, 'DLLs', 'tk86t.dll'),
            os.path.join(PYTHON_INSTALL_DIR, 'DLLs', 'tcl86t.dll'),
         ],
         'build_exe': "build"
    },
}

setup(options = options,
    name = "HDR Brackets" ,
    version = "0.1" ,
    description = "" ,
    buildOptions = dict(packages = ['exifread'], excludes = []),
    executables = [Executable(script="hdr_brackets.py", base=None, icon="icons/icon.ico")])