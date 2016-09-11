
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
            return self.root.senslevel == 2
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
    entry = None
    def __init__(self, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remember entry
        self.entry = entry
        # name
        if self.entry[3]:
            self.text = "{} ({})".format(self.entry[3], self.entry[0])
        else:
            self.text=self.entry[0]

class ChatAvailTreeNode(GridLayout, TreeViewNode):
    certhash = None
    def __init__(self, certhash, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remember entry
        self.certhash = certhash
        # name
        self.add_widget(Label(text=self.certhash))

class MainWidget(Widget):
    requester = None
    pwhandler = None
    pathchats = None
    senslevel = 0

    def async_load(self, func,  *args, **kwargs):
        print("loadfriends")
        time.sleep(0.6)
        threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()
    
    def set_sensitivelabel(self, widget):
        val = int(widget.value)
        if val == 0:
            self.ids["senslabel"].text = chatscn.senslevel_to_text(val)
            self.ids["senslabel"].color = (0., 1., 0., 1.)
        elif val == 1:
            self.ids["senslabel"].text = chatscn.senslevel_to_text(val)
            self.ids["senslabel"].color = (0.8, 0., 0., 1.)
        elif val == 2:
            self.ids["senslabel"].text = chatscn.senslevel_to_text(val)
            self.ids["senslabel"].color = (1., 0.6, 0.2, 1.)
        if val < 2 and self.senslevel >= 2:
            pass
        self.senslevel = val

    def load_friends(self):
        lnames1 = self.requester.do_request_simple("/client/listnodeall", {"filter": "client"}, {})
        if not logcheck(lnames1):
            return
        wid = self.ids.get("friendlist")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        for entry in lnames1[1]["items"]:
            wid.add_node(FriendTreeNode(entry))

    def registerserver(self):
        serverurlw = self.ids["serveraddressinp"]
        reg1 = self.requester.do_request_simple("/client/register", {"server": serverurlw.text}, {})
        if logcheck(reg1):
            self.load_servernames()

    def load_servernames(self):
        serverurlw = self.ids["serveraddressinp"]
        serverurlw.background_color = (1., 1., 1., 1.)
        nameofserver = self.ids["nameofserver"]
        nameofserver.text = ""
        lnames1 = self.requester.do_request_simple("/client/listnames", {"server": serverurlw.text}, {})
        if not logcheck(lnames1):
            if serverurlw.text != "":
                serverurlw.background_color = (1., 0., 0., 1.)
            return
        if not lnames1[2]:
            nameofserver.text = "unknown"
        elif lnames1[2] is isself:
            nameofserver.text = "Own client"
        else:
            nameofserver.text = "Identified as:\n{}".format(lnames1[2][0])
        wid = self.ids.get("serverlist")
        for node in wid.iterate_all_nodes():
            if node.parent_node:
                wid.remove_node(node)
        entryfriends = set()
        self.ids["registerserverb"].text = "Register"
        for entry in lnames1[1]["items"]:
            if entry[2] != "valid":
                continue
            if entry[3]:
                if entry[3] in entryfriends:
                    continue
                elif entry[3] == isself:
                    self.ids["registerserverb"].text = "Register again"
                    continue
                else:
                    entryfriends.add(entry[3])
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
    _client_address = None
    _client_use_unix = None
    
    def __init__(self, address, use_unix, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client_address = address
        self._client_use_unix = use_unix
        
    def build(self):
        self.title = "ChatSCN"
        self.icon = os.path.join(chatscn.thisdir, 'icon.png')
    
    def on_start(self):
        requester = Requester(pwhandler=self.root.pwhandler, use_unix=self._client_use_unix)
        self.root.pathchats = os.path.join(self.user_data_dir, "chats")
        os.makedirs(self.root.pathchats, mode=0o700, exist_ok=True)
        self.root.requester = chatscn.SCNSender(self._client_address, requester, self.root.pathchats)
        self.root.hserver = chatscn.init(self.root.requester, genHandler(self.root, self.root.pathchats))
        if not self.root.hserver:
            raise


def open(address, use_unix):
    bal = ChatSCNApp(address, use_unix)
    bal.run()
