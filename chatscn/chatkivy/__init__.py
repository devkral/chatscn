
import kivy
kivy.require('1.9.1')

import threading
import os
import io
import json

from kivy.app import App
#from kivy.uix.pagelayout import PageLayout
from kivy.uix.treeview import TreeViewNode
from kivy.uix.gridlayout import GridLayout
#from kivy.uix.boxlayout import BoxLayout
#from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.properties import ListProperty
#from kivy.uix.behaviors import DragBehavior
#from kivy.graphics import Color
#from  kivy.graphics.vertex_instructions import Point
#, StringProperty

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
            if self.root.cur_hash != indict["certhash"]:
                return
            chathist = self.root.ids["chathist"]
            chathist.add_node(ChatTreeNode(indict))

        def issensitive(self):
            return self.root.senslevel == 2
    return KivyHandler

class ChatTreeNode(FloatLayout, TreeViewNode):
    def __init__(self, indict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(indict)
        if indict["owner"]:
            size = (0.7, 1)
            pos = {"x": 0.3, "y":0}
        else:
            size = (0.7, 1)
            pos = {"x": 0, "y":0}
        if indict["type"] == "text":
            self.height = 30
            self.add_widget(Label(text=indict["text"], size_hint=size, pos_hint=pos))
        elif indict["type"] == "image":
            self.height = 100
            l = io.BytesIO(bytes(indict["image"], "utf-8"))
            self.add_widget(Image(source=l, size_hint=size, pos_hint=pos))
        elif indict["type"] == "file":
            pass
        else:
            raise

class FriendTreeNode(GridLayout, TreeViewNode):
    entry = None

    def __init__(self, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry = entry
        # name
        self.add_widget(Label(text=self.entry[0]))
        # security
        self.add_widget(Label(text=self.entry[4]))

    def on_touch_down(self, touch):
        if touch.is_triple_tap:
            pass
        elif touch.is_double_tap:
            ids = App.get_running_app().root.ids
            ids["convershash"].text = self.entry[1]
            ids["screenman"].current = "chats"
            ids["chatbutton"].state = "down"
            ids["serverbutton"].state = "normal"
        #    super(TreeViewNode, self). on_touch_move(touch)


class ServerTreeNode(Label, TreeViewNode):
    def __init__(self, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry = entry
        # name
        if self.entry[3]:
            self.text = "{} ({})".format(self.entry[3], self.entry[0])
        else:
            self.text=self.entry[0]

    def on_touch_down(self, touch):
        if touch.is_triple_tap:
            pass
        elif touch.is_double_tap:
            ids = App.get_running_app().root.ids
            ids["convershash"].text = "{}/{}".format(self.entry[0], self.entry[1])
            ids["screenman"].current = "chats"
            ids["chatbutton"].state = "down"
            ids["serverbutton"].state = "normal"



class ChatAvailTreeNode(GridLayout, TreeViewNode):
    certhash = None
    def __init__(self, certhash, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.certhash = certhash
        # name
        b = Button(text=self.certhash)
        b.bind(on_press=self.load_conversation)
        self.add_widget(b)
    
    def load_conversation(self, instance):
        root = App.get_running_app().root
        root.ids["convershash"].text = self.certhash


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
    cur_hash = ""
    cur_name = None
    _popup = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pwhandler(self, msg):
        self._popup = Popup(title="Password Required", content=PwDialog(msg), size_hint=(0.9, 0.5))
        self._popup.open()
    
    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()
    
    def set_namehash(self, text):
        splitted= text.rsplit("/", 1)
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

    def send_image(self):
        self._popup = Popup(title="Load Image", content=ImageDialog(), size_hint=(0.9, 0.9))
        self._popup.open()

    def _send_image(self, selectedfiles, caption):
        self.dismiss_popup()
        if not selectedfiles or len(selectedfiles) == 0:
            return
        if self.cur_hash == "":
            return
        if caption.strip() == "":
            caption = None
        self.requester.send_image(self.cur_hash, self.senslevel, selectedfiles[0], caption=caption, name=self.cur_name)

    def send_file(self):
        buttons = [("Send", self._send_file), ("Cancel", lambda selection: self.dismiss_popup())]
        self._popup = Popup(title="Load File", content=FileDialog(buttons=buttons), size_hint=(0.9, 0.9))
        self._popup.open()
    
    def _send_file(self, selectedfiles):
        self.dismiss_popup()
        if not selectedfiles or len(selectedfiles) == 0:
            return
        if self.cur_hash == "":
            return
        self.requester.send_file(self.cur_hash, self.senslevel, selectedfiles[0], name=self.cur_name)


    def load_friends(self):
        lnames1 = self.requester.requester.do_request("/client/listnodeall", {"filter": "client"}, {})
        if not logcheck(lnames1):
            return
        wid = self.ids.get("friendlist")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        for entry in lnames1[2]["items"]:
            wid.add_node(FriendTreeNode(entry))

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
        for node in wid.iterate_all_nodes():
            if node.parent_node:
                wid.remove_node(node)
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
            wid.add_node(ServerTreeNode(entry))

    def load_avail_chats(self):
        os.makedirs(self.pathchats, mode=0o700, exist_ok=True)
        wid = self.ids.get("chatfriends")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        for centry in os.listdir(self.pathchats):
            if check_hash(centry):
                wid.add_node(ChatAvailTreeNode(centry))
 
    def load_conversation(self):
        _hash = self.cur_hash
        if not check_hash(_hash):
            return
        p = os.path.join(self.pathchats, _hash)
        os.makedirs(p, mode=0o700, exist_ok=True)
        wid = self.ids.get("chathist")
        for node in wid.iterate_all_nodes():
            wid.remove_node(node)
        setnum = set()
        setnum.update(filter(lambda x: x.split(".", 1)[0].isdecimal(), os.listdir(p)))
        hbuf = chatscn.messagebuffer.get(_hash, {})
        setnum.update(hbuf.keys())
        for num in sorted(setnum):
            if num in hbuf:
                wid.add_node(ChatTreeNode(hbuf[num]))
            elif isinstance(num, str) and os.path.exists(os.path.join(p, num)):
                with open(os.path.join(p, num), "r") as ro:
                    try:
                        wid.add_node(ChatTreeNode(json.load(ro)))
                    except Exception as exc:
                        print(exc)


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

    def async_load(self, func,  *args, **kwargs):
        threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()

def openchat(address, use_unix):
    bal = ChatSCNApp()
    bal.requester = Requester(addrcon=address, use_unix=use_unix)
    bal.run()
