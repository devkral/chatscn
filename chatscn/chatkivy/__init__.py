
import kivy
kivy.require('1.9.1')

from kivy.app import App
from kivy.uix.widget import Widget
#from kivy.uix.pagelayout import PageLayout

from simplescn.scnrequest import Requester

import chatscn

def genHandler(rootwidget):
    class KivyHandler(chatscn.ChatHandler):
        root = rootwidget
        def notify(self, indict):
            pass

        def issensitive(self):
            pass
        basedir = None
    return KivyHandler

class MainWidget(Widget):
    client_address = None
    client_use_unix = None
    requester = None
    pwhandler = None

class ChatSCNApp(App):
    hserver = None
    def __init__(self, address, use_unix, *args, **kwargs):
        super().__init__(*args,  **kwargs)
        MainWidget.client_address = address
        MainWidget.client_use_unix = use_unix
        
    def build(self):
        self.title = "ChatSCN"
    
    def on_start(self):
        self.root.requester = Requester(pwhandler=self.root.pwhandler, use_unix=self.root.client_use_unix)
        self.root.hserver = chatscn.init(self.root.requester, self.root.client_address, KivyHandler)
        if not self.root.hserver:
            raise
        

def open(address, use_unix):
    bal = ChatSCNApp(address, use_unix)
    bal.run()
