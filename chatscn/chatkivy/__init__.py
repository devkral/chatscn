
import kivy
kivy.require('1.9.1')

import threading
import os
from kivy.app import App
#from kivy.uix.pagelayout import PageLayout
from kivy.uix.treeview import TreeViewNode
from kivy.uix.gridlayout import GridLayout
#from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import ListProperty, StringProperty

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
    entry = ListProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # name
        self.add_widget(Label(text=self.entry[0]))
        # security
        self.add_widget(Label(text=self.entry[4]))

class ServerTreeNode(Label, TreeViewNode):
    entry = ListProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # name
        if self.entry[3]:
            self.text = "{} ({})".format(self.entry[3], self.entry[0])
        else:
            self.text=self.entry[0]

class ChatAvailTreeNode(GridLayout, TreeViewNode):
    certhash = StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # name
        self.add_widget(Label(text=self.certhash))

class ImageDialog(FloatLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class FileDialog(FloatLayout):
    buttons = ListProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_buttons(self.buttons, self.buttons)
    
    def on_buttons(self, instance, value):
        if "selectedfile" not in self.ids:
            return
        for elem in self.buttons:
            name, func = elem
            b = Button(text=name)
            b.bind(on_press=lambda butinstance: func(self.ids["selectedfile"].selection))
            self.ids["buttonlist"].add_widget(b)

class ChatView(FloatLayout):
    pass
class PwDialog(FloatLayout):
    msg = None
    def __init__(self, *args, **kwargs):
        self.msg = None
        super().__init__( *args, **kwargs)
        #self.ids["msg"] = msg

class MainWidget(FloatLayout):
    requester = None
    pathchats = None
    senslevel = 0
    _popup = None

    def __init__(self, *args, **kwargs):
        super().__init__( *args, **kwargs)

    def pwhandler(self, msg):
        self._popup = Popup(title="Password Required", content=PwDialog(msg), size_hint=(0.9, 0.5))
        self._popup.open()
    
    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()

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

    def registerserver(self):
        serverurlw = self.ids["serveraddressinp"]
        reg1 = self.requester.requester.do_request_simple("/client/register", {"server": serverurlw.text}, {})
        if logcheck(reg1):
            self.load_servernames()
    
    def send_text(self):
        chattext = self.ids["chattext"]
        certhash = self.ids["convershash"].text
        if certhash == "":
            return
        ret = self.requester.send_text(certhash, self.senslevel, chattext.text)
        if ret:
            chattext.text = ""

    def send_image(self):
        self._popup = Popup(title="Load Image", content=ImageDialog(), size_hint=(0.9, 0.9))
        self._popup.open()

    def _send_image(self, selectedfiles, caption):
        self.dismiss_popup()
        if not selectedfiles or len(selectedfiles) == 0:
            return
        certhash = self.ids["convershash"].text
        if certhash == "":
            return
        if caption.strip() == "":
            caption = None
        self.requester.send_image(certhash, self.senslevel, selectedfiles[0], caption=caption)

    def send_file(self):
        buttons = [("Send", self._send_file), ("Cancel", lambda selection: self.dismiss_popup())]
        self._popup = Popup(title="Load File", content=FileDialog(buttons=buttons), size_hint=(0.9, 0.9))
        self._popup.open()
    
    def _send_file(self, selectedfiles):
        self.dismiss_popup()
        if not selectedfiles or len(selectedfiles) == 0:
            return
        certhash = self.ids["convershash"].text
        if certhash == "":
            return
        self.requester.send_file(certhash, self.senslevel, selectedfiles[0])


    def load_friends(self):
        lnames1 = self.requester.do_request_simple("/client/listnodeall", {"filter": "client"}, {})
        if not logcheck(lnames1):
            return
        wid = self.ids.get("friendlist")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        for entry in lnames1[1]["items"]:
            wid.add_node(FriendTreeNode(entry=entry))

    def load_servernames(self):
        serverurlw = self.ids["serveraddressinp"]
        serverurlw.background_color = (1., 1., 1., 1.)
        nameofserver = self.ids["nameofserver"]
        nameofserver.text = ""
        _reqserver = serverurlw.text
        lnames1 = self.requester.requester.do_request_simple("/client/listnames", {"server": _reqserver}, {})
        if not logcheck(lnames1):
            if _reqserver != "":
                serverurlw.background_color = (1., 0., 0., 1.)
            return
        self.requester.cur_server = _reqserver
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
                wid.add_node(ServerTreeNode(entry=entry))

    def load_avail_chats(self):
        os.makedirs(self.pathchats, mode=0o700, exist_ok=True)
        wid = self.ids.get("chatfriends")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        for centry in os.listdir(self.pathchats):
            if check_hash(centry):
                wid.add_node(ChatAvailTreeNode(certhash=centry))

class ChatSCNApp(App):
    requester = None
    def __init__(self, address, use_unix, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requester = Requester(default_addrcon=address, use_unix=use_unix)
        
    def on_start(self):
        self.requester.saved_kwargs["pwhandler"] = self.root.pwhandler
        self.root.pathchats = os.path.join(self.user_data_dir, "chats")
        os.makedirs(self.root.pathchats, mode=0o700, exist_ok=True)
        self.root.requester = chatscn.SCNSender(self.requester, MainWidget.pathchats)
        MainWidget.hserver = chatscn.init(self.root.requester, genHandler(self.root, MainWidget.pathchats))
        if not MainWidget.hserver:
            raise

    def build(self):
        self.title = "ChatSCN"
        self.icon = os.path.join(chatscn.thisdir, 'icon.png')

    def async_load(self, func,  *args, **kwargs):
        threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()

def open(address, use_unix):
    bal = ChatSCNApp(address, use_unix)
    bal.run()
