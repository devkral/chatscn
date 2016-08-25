
import kivy
kivy.require('1.9.1')

from kivy.app import App
from kivy.uix.widget import Widget
#from kivy.uix.pagelayout import PageLayout

from simplescn.scnrequest import Requester
from simplescn.tools import logcheck

import chatscn

def genHandler(rootwidget):
    class KivyHandler(chatscn.ChatHandler):
        root = rootwidget
        def notify(self, indict):
            pass

        def issensitive(self):
            # stub
            return False
        basedir = None
    return KivyHandler

class MainWidget(Widget):
    client_address = None
    client_use_unix = None
    requester = None
    pwhandler = None

    def load_friends(self):
        lnames1 = self.requester.do_request_simple(self.client_address, "/client/listnames", {}, {})
        wid = self.ids.get("friendlist")
        if not logcheck(lnames1):
            return
        
        for _name, _hash, _security, _localname in lnames1[1]:
            wid.add_node(TreeViewLabel(text=_name))
    
    def load_chats():
        pass

class ChatSCNApp(App):
    hserver = None
    def __init__(self, address, use_unix, *args, **kwargs):
        super().__init__(*args, **kwargs)
        MainWidget.client_address = address
        MainWidget.client_use_unix = use_unix
        
    def build(self):
        self.title = "ChatSCN"
    
    def on_start(self):
        self.root.requester = Requester(pwhandler=self.root.pwhandler, use_unix=self.root.client_use_unix)
        self.root.hserver = chatscn.init(self.root.requester, self.root.client_address, genHandler(self.root))
        if not self.root.hserver:
            raise
        self.root.load_friends()
    

def open(address, use_unix):
    bal = ChatSCNApp(address, use_unix)
    bal.run()
