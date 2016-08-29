
import kivy
kivy.require('1.9.1')

import threading
import time
import os
from kivy.app import App
from kivy.uix.widget import Widget
#from kivy.uix.pagelayout import PageLayout
from kivy.uix.treeview import TreeViewNode
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label


from simplescn.scnrequest import Requester
from simplescn.tools import logcheck
from simplescn.tools.checks import check_hash
from simplescn.config import isself

import chatscn

def genHandler(rootwidget, chatdirectory):
    class KivyHandler(chatscn.ChatHandler):
        root = rootwidget
        basedir = chatdirectory
        def notify(self, indict):
            pass

        def issensitive(self):
            # stub
            return False
    return KivyHandler


class FriendTreeNode(GridLayout, TreeViewNode):
    entry = None
    def __init__(self, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remember entry
        self.entry = entry
        # name
        self.add_widget(Label(text=self.entry[0]))
        # security
        self.add_widget(Label(text=self.entry[4]))

class ServerTreeNode(Label, TreeViewNode):
    pass

class ChatAvailTreeNode(GridLayout, TreeViewNode):
    certhash = None
    def __init__(self, certhash, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remember entry
        self.certhash = certhash
        # name
        self.add_widget(Label(text=self.certhash))
        

class MainWidget(Widget):
    client_address = None
    client_use_unix = None
    requester = None
    pwhandler = None
    pathchats = None

    def async_load(self, func,  *args, **kwargs):
        time.sleep(0.6)
        threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()

    def load_friends(self):
        lnames1 = self.requester.do_request_simple(self.client_address, "/client/listnodeall", {"filter": "client"}, {})
        if not logcheck(lnames1):
            return
        wid = self.ids.get("friendlist")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        for entry in lnames1[1]["items"]:
            wid.add_node(FriendTreeNode(entry))

    def load_servernames(self):
        serverurlw = self.ids["serveraddressinp"]
        serverurlw.background_color = (1., 1., 1., 1.)
        nameofserver = self.ids["nameofserver"]
        nameofserver.text = ""
        lnames1 = self.requester.do_request_simple(self.client_address, "/client/listnames", {"server": serverurlw.text}, {})
        if not logcheck(lnames1):
            if serverurlw.text != "":
                serverurlw.background_color = (1., 0., 0., 1.)
            return
        if not lnames1[2]:
            nameofserver.text = "unknown"
        elif lnames1[2] is isself:
            nameofserver.text = "Own client"
        else:
            nameofserver.text = "Identified as: {}".format(lnames1[2][0])
        wid = self.ids.get("serverlist")
        for node in wid.iterate_all_nodes():
            if node.parent_node:
                wid.remove_node(node)
        for entry in lnames1[1]["items"]:
            if entry[2] == "valid":
                wid.add_node(ServerTreeNode(entry))

    def load_avail_chats(self):
        os.makedirs(self.pathchats, mode=0o700, exist_ok=True)
        wid = self.ids.get("chatfriends")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        for centry in os.listdir(self.pathchats):
            if check_hash(centry):
                wid.add_node(ChatAvailTreeNode(centry))

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
        self.root.pathchats = os.path.join(self.user_data_dir, "chats")
        os.makedirs(self.root.pathchats, mode=0o700, exist_ok=True)
        self.root.hserver = chatscn.init(self.root.requester, self.root.client_address, genHandler(self.root, self.root.pathchats))
        if not self.root.hserver:
            raise
        #self.root.load_friends()
    

def open(address, use_unix):
    bal = ChatSCNApp(address, use_unix)
    bal.run()
