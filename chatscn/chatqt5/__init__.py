
import threading
import os
import sys
import json
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtQml import QQmlComponent, QQmlEngine
from PyQt5.QtCore import QUrl, QStandardPaths

from simplescn.scnrequest import Requester
from simplescn.tools import logcheck
from simplescn.tools.checks import check_hash
from simplescn.config import isself
from simplescn import pwrequester

import chatscn
def genHandler(rootwidget, chatdirectory):
    class QT5Handler(chatscn.ChatHandler):
        root = rootwidget
        basedir = chatdirectory
        def notify(self, indict):
            self.root.notify(indict)

        def issensitive(self):
            return self.root.senslevel == 2
    return QT5Handler

class qt5chat(object):
    app = None
    engine = None
    requester = None
    basedir = None
    def __init__(self, requester):
        self.requester = requester
        self.app = QApplication(sys.argv)
        self.basedir = QStandardPaths.writableLocation(QStandardPaths.DataLocation)
        # Create a QML engine.
        self.engine = QQmlEngine()

        # Create a component factory and load the QML script.
        component = QQmlComponent(self.engine)
        component.loadUrl(QUrl('example.qml'))
        self.hserver = chatscn.init(requester, genHandler(self.app, self.basedir))
        if not self.hserver:
            raise

    def run(self):
        return self.app.exec_()
def openchat(address, use_unix):
    requester = Requester(addrcon=address, use_unix=use_unix)

