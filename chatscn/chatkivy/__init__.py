
import kivy
kivy.require('1.9.1')

import threading
import os
import json
import logging

from kivy.app import App
#from kivy.uix.pagelayout import PageLayout
from kivy.uix.treeview import TreeView, TreeViewNode
from kivy.uix.gridlayout import GridLayout
#from kivy.uix.boxlayout import BoxLayout
#from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
#from kivy.graphics import Color
#from  kivy.graphics.vertex_instructions import Point
#, StringProperty

from simplescn.scnrequest import Requester
from simplescn.tools import logcheck
from simplescn.tools.checks import check_hash
from simplescn.config import isself

import chatscn
from chatscn.chatkivy.nodes import ChatNode, PwDialog, FileDialog, ServerTreeNode, FriendTreeNode, ChatAvailTreeNode
from chatscn.chatkivy.dialogs import PopupNew

def genHandler(rootwidget, chatdirectory):
    class KivyHandler(chatscn.ChatHandler):
        root = rootwidget
        basedir = chatdirectory
        def notify(self, indict):
            self.root.notify(indict)

        def issensitive(self):
            return self.root.senslevel == 2
    return KivyHandler

class TreeViewButton(Button, TreeViewNode):
    pass

class ScrollGrid(GridLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind(minimum_height=self.setter('height'))

class ScrollTree(TreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind(minimum_height=self.setter('height'))


class ChatView(FloatLayout):
    pass
        #self.dismiss()
class MainWidget(FloatLayout):
    requester = None
    pathchats = None
    senslevel = 0
    cur_hash = ""
    cur_name = None
    popup = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def notify(self, indict):
        if not indict:
            return
        if self.cur_hash != indict["certhash"]:
            #wi = self.ids["chatfriends"]
            #wi.add_widget()
            return
        chathist = self.ids["chathist"]
        chathist.add_widget(ChatNode(indict))

    def pwhandler(self, msg):
        self.popup = PopupNew(title="Password Required", content=PwDialog(msg), size_hint=(0.9, 0.5))
        self.popup.open()

    def dismiss_popup(self):
        if self.popup:
            self.popup.dismiss()

    def set_namehash(self, text):
        splitted = text.rsplit("/", 1)
        if len(splitted) == 2:
            self.cur_name, self.cur_hash = splitted
        else:
            self.cur_name, self.cur_hash = None, splitted[0]
        self.load_conversation()

    def set_sensitivelabel(self, widget):
        val = int(widget.value)
        if val == 0:
            self.ids["senslabel"].text = chatscn.senslevel_to_text(val)
            self.ids["senslabel"].disabled_color = (0., 1., 0., 1.)
        elif val == 1:
            self.ids["senslabel"].text = chatscn.senslevel_to_text(val)
            self.ids["senslabel"].disabled_color = (0.8, 0., 0., 1.)
        elif val == 2:
            self.ids["senslabel"].text = chatscn.senslevel_to_text(val)
            self.ids["senslabel"].disabled_color = (1., 0.6, 0.2, 1.)
        if val < 2 and self.senslevel >= 2:
            pass
        self.senslevel = val

    def registerserver(self):
        serverurlw = self.ids["serveraddressinp"]
        serverurlt = serverurlw.text
        if serverurlt == "":
            return
        reg1 = self.requester.requester.do_request("/client/register", {"server": serverurlt}, {})
        if logcheck(reg1):
            self.load_servernames()

    def send_text(self):
        chattext = self.ids["chattext"]
        if self.cur_hash == "":
            return
        ret = self.requester.send_text(self.cur_hash, self.senslevel, chattext.text, name=self.cur_name)
        if ret:
            chattext.text = ""
            self.notify(ret)

    def send_image(self):
        buttons = [("Send", self._send_image), ("Cancel", lambda selection, x: self.dismiss_popup())]
        self.popup = PopupNew(title="Load Image", content=FileDialog(buttons=buttons, label="Caption"), size_hint=(0.9, 0.9))
        self.popup.open()

    def _send_image(self, selectedfiles, caption):
        self.dismiss_popup()
        if not selectedfiles or len(selectedfiles) == 0:
            return
        if self.cur_hash == "":
            return
        if caption.strip() == "":
            caption = None
        ret = self.requester.send_image(self.cur_hash, self.senslevel, selectedfiles[0], caption=caption, name=self.cur_name)
        if ret:
            self.notify(ret)

    def send_file(self):
        buttons = [("Send", self._send_file), ("Cancel", lambda selection, x: self.dismiss_popup())]
        self.popup = PopupNew(title="Load File", content=FileDialog(buttons=buttons), size_hint=(0.9, 0.9))
        self.popup.open()

    def _send_file(self, selectedfiles, name):
        self.dismiss_popup()
        if not selectedfiles or len(selectedfiles) == 0:
            return
        if self.cur_hash == "":
            return
        ret = self.requester.send_file(self.cur_hash, self.senslevel, selectedfiles[0], filename=name, name=self.cur_name)
        if ret:
            self.notify(ret)


    def load_friends(self):
        lnames1 = self.requester.requester.do_request("/client/listnodenames", {"filter": "client"}, {})
        if not logcheck(lnames1):
            return
        wid = self.ids.get("friendlist")
        wid.clear_widgets()
        for entry in lnames1[2]["items"]:
            wid.add_widget(FriendTreeNode(entry))

    def load_servernames(self):
        serverurlw = self.ids["serveraddressinp"]
        serverurlw.background_color = (1., 1., 1., 1.)
        nameofserver = self.ids["nameofserver"]
        nameofserver.text = ""
        _reqserver = serverurlw.text
        lnames1 = self.requester.requester.do_request("/client/listnames", {"server": _reqserver}, {})
        if not logcheck(lnames1):
            if _reqserver != "":
                serverurlw.background_color = (1., 0., 0., 1.)
            return
        self.requester.cur_server = _reqserver
        if not lnames1[3][0]:
            nameofserver.text = "unknown"
        elif lnames1[3][0] is isself:
            nameofserver.text = "Own client"
        else:
            nameofserver.text = "Identified as:\n{}".format(lnames1[3][0][0])
        wid = self.ids.get("serverlist")
        wid.clear_widgets()
        entryfriends = set()
        self.ids["registerserverb"].text = "Register"
        for entry in lnames1[2]["items"]:
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
            wid.add_widget(ServerTreeNode(entry))

    def load_avail_chats(self):
        os.makedirs(self.pathchats, mode=0o700, exist_ok=True)
        wid = self.ids.get("chatfriends")
        wid.clear_widgets()
        l = set()
        group = "ChatAvail"
        for centry in os.listdir(self.pathchats):
            if check_hash(centry):
                ret = self.requester.requester.do_request("/client/getlocal", {"hash": centry}, {})
                if ret[0]:
                    name = ret[2].get("name")
                    if name in l:
                        continue
                    l.add(name)
                else:
                    name = None
                wid.add_widget(ChatAvailTreeNode(centry, localname=name, group=group))

    def load_conversation(self):
        _hash = self.cur_hash
        if not check_hash(_hash):
            return
        p = os.path.join(self.pathchats, _hash)
        os.makedirs(p, mode=0o700, exist_ok=True)
        wid = self.ids.get("chathist")
        wid.clear_widgets()
        hbuf = chatscn.messagebuffer.get(_hash, {})
        setnum = []
        for elem in os.listdir(p):
            splitted = elem.split(".", 1)
            if splitted[0].isdecimal():
                setnum.append(int(splitted[0]))
        setnum += hbuf.keys()
        for num in sorted(setnum):
            if not isinstance(num, int):
                logging.error("Error: wrong type %s (%s)", num, type(num))
                continue
            if num in hbuf:
                wid.add_widget(ChatNode(hbuf[num]))
            else:
                jp = os.path.join(p, "{}.json".format(num))
                if os.path.exists(jp):
                    with open(jp, "r") as ro:
                        try:
                            wid.add_widget(ChatNode(json.load(ro)))
                        except Exception:
                            logging.error("%s caused error", jp)


class ChatSCNApp(App):
    requester = None

    def on_start(self):
        self.requester.p.keywords["pwhandler"] = self.root.pwhandler
        self.root.pathchats = os.path.join(self.user_data_dir, "chats")
        os.makedirs(self.root.pathchats, mode=0o700, exist_ok=True)
        self.root.requester = chatscn.SCNSender(self.requester, self.root.pathchats)
        self.root.hserver = chatscn.init(self.root.requester, genHandler(self.root, self.root.pathchats))
        if not self.root.hserver:
            raise
        # on enter fires only if switched
        self.root.load_avail_chats()

    def build(self):
        self.title = "ChatSCN"
        self.icon = os.path.join(chatscn.thisdir, 'icon.png')
        #ch = self.root.ids["chathist"]
        #ch.bind(minimum_height=ch.setter('height'))

    def async_load(self, func,  *args, **kwargs):
        # needed for kv file
        threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()

def openchat(address, use_unix):
    bal = ChatSCNApp()
    bal.requester = Requester(addrcon=address, use_unix=use_unix)
    bal.run()
