
import os
import sys
import importlib
from simplescn.tools import getlocalclient, start

thisdir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if thisdir not in sys.path:
    sys.path.insert(0, thisdir)

def openfoo(modulename, address, use_unix):
    try:
        module = importlib.import_module(modulename, "chatscn.__main__")
        module.open(address, use_unix)
    except ImportError:
        return False

def open_gui(address, use_unix):
    if openfoo("chatkivy", address, use_unix):
        return

if __name__ == "__main__":
    if len(sys.argv) == 2:
        if os.path.exists(sys.argv[1]):
            open_gui(sys.argv[1], use_unix=True)
        else:
            open_gui(sys.argv[1], use_unix=False)
    else:
        p = getlocalclient()
        if not p:
            ret = start.client([], doreturn=True)
            if ret:
                start.running_instances.append(ret)
            p = getlocalclient()
        if p:
            open_gui(*p)
        else:
            print("Starting client failed")
