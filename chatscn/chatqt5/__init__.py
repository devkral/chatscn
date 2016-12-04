
import threading
import os
import sys
import json
import logging
import time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel
#from PyQt5.QtQml import QQmlComponent, QQmlEngine
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


class ChatMainWin(QWidget):
    app = None
    engine = None
    requester = None
    basedir = None
    def __init__(self, requester, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requester = chatscn.SCNSender(requester, self.basedir)
        self.initUI()

    def initUI(self):
        grid = QGridLayout()
        self.setLayout(grid)
        self.basedir = os.path.join(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation), "chatscn")
        print(self.basedir)
        title = QLabel('Title')
        grid.addWidget(title, 0, 0)

        self.setGeometry(300, 300, 350, 300)
        self.setWindowTitle('Review')
        self.activateWindow()
        self.show()

        # Create a QML engine.
        #self.engine = QQmlEngine()
        # Create a component factory and load the QML script.
        #component = QQmlComponent(self.engine)
        #component.loadUrl(QUrl('example.qml'))

        self.hserver = chatscn.init(self.requester, genHandler(self, self.basedir))
        if not self.hserver:
            raise

def openchat(address, use_unix):
    app = QApplication([])
    requester = Requester(addrcon=address, use_unix=use_unix)
    ChatMainWin(requester)
    app.exec_()
