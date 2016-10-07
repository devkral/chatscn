
import kivy
kivy.require('1.9.1')

import threading
import os
import io
import json
import logging

from kivy.app import App
#from kivy.uix.pagelayout import PageLayout
from kivy.uix.treeview import TreeView#, TreeViewNode
from kivy.uix.gridlayout import GridLayout
#from kivy.uix.boxlayout import BoxLayout
#from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.properties import ListProperty, StringProperty
from kivy.uix.bubble import BubbleButton, Bubble
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
            self.root.notify(indict)

        def issensitive(self):
            return self.root.senslevel == 2
    return KivyHandler

class ScrollGrid(GridLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind(minimum_height=self.setter('height'))

class ScrollTree(TreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind(minimum_height=self.setter('height'))


class UseBubble(object):
    bubble = None

    def openbubble(self, buttonfunclist):
        if self.bubble:
            logging.error("Bubble already called")
            return
        self.bubble = Bubble(height=30, width=60*len(buttonfunclist), pos=self.to_window(self.x, self.y+30), size_hint=(None, None))
        for text, func in buttonfunclist:
            button = BubbleButton(text=text, height=30)
            self.call(button, func)
            self.bubble.add_widget(button)
        root = App.get_running_app().root
        #self.get_root_window().add_widget(self.bubble, root.canvas)
        root.add_widget(self.bubble)

    def closebubble(self):
        if self.bubble:
            #self.get_root_window().remove_widget(self.bubble)
            root = App.get_running_app().root
            root.clear_widgets([self.bubble])
            self.bubble = None
    def call(self, button, funccall):
        def _call(instance):
            self.closebubble()
            return funccall()
        button.bind(on_press=_call)


class DeleteDialog(FloatLayout):
    buttons = ListProperty()
    message = StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_buttons(self.buttons, None)
        self.on_message(self.message, None)

    def on_buttons(self, instance, value):
        if "buttonlist" not in self.ids:
            return
        for elem in self.buttons:
            name, func = elem
            b = Button(text=name)
            b.bind(on_press=func())
            self.ids["buttonlist"].add_widget(b)

    def on_message(self, instance, value):
        if "deletemsg" not in self.ids:
            return
        self.ids["deletemsg"].text = instance

class HashDialog(FloatLayout):
    pass

class ChatNode(FloatLayout):
    def __init__(self, indict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if indict["owner"]:
            size = (0.6, 1)
            pos = {"x": 0.2, "y":0}
            #self.add_widget(Label(text="self", size_hint=(0.05, 1), pos_hint={"x": 0, "y":0}))
        else:
            size = (0.6, 1)
            pos = {"x": 0, "y":0}
        if indict["type"] == "text":
            #self.height = 30*(indict["text"].count("\n")+1)
            l = Label(text=indict["text"], size_hint=size, pos_hint=pos, halign='left')
            self.add_widget(l)
            l.texture_update()
            #print(l.size, l.texture_size, self.size, self.pos, l.pos)
        elif indict["type"] == "image":
            #self.height = 100
            l = io.BytesIO(bytes(indict["image"], "utf-8"))
            self.add_widget(Image(source=l, size_hint=size, pos_hint=pos))
        elif indict["type"] == "file":
            pass
        else:
            raise

class FriendTreeNode(UseBubble, Button):
    entry = None

    def __init__(self, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry = entry
        #self.border=(0, 0, 0, 0)
        # name
        self.text = self.entry[0]
        # security
        if self.entry[4] != "valid":
            self.color = (1, 0, 0, 1)
        #self.add_widget(Label(text=self.entry[4]))

    def on_press(self):
        if self.bubble:
            self.closebubble()
        else:
            self.openbubble([("Load", self.load_friend), ("Rename", lambda:print("TODO")), ("Delete", self.delete_friend)])

    def load_friend(self):
        ids = App.get_running_app().root.ids
        ids["convershash"].text = "{}/{}".format(self.entry[0], self.entry[1])
        ids["screenman"].current = "chats"
        ids["chatbutton"].state = "down"
        ids["serverbutton"].state = "normal"

    def delete_friend(self):
        root = App.get_running_app().root
        buttonlist = [("Delete", self.delete_friend_aftercheck), ("Cancel", root.dismiss_popup)]
        msg = 'Really delete friend: "{}"?'.format(self.entry[0])
        dia = DeleteDialog(message=msg, buttons=buttonlist)
        root.popup = Popup(title="Confirm Deletion", content=dia, size_hint=(0.9, 0.5))
        root.popup.open()

    def delete_friend_aftercheck(self):
        root = App.get_running_app().root
        root.dismiss_popup()
        ret = root.requester.requester.do_request("/client/delentity", {"name":self.entry[0]})
        if logcheck(ret):
            root.load_friends()
        #super(TreeViewNode, self). on_touch_move(touch)

class ServerTreeNode(UseBubble, Button):
    def __init__(self, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry = entry
        # name
        if self.entry[3]:
            self.text = self.entry[3]
            self.color = (0, 1, 0, 1)
        else:
            self.text = self.entry[0]

    def on_press(self):
        if self.bubble:
            self.closebubble()
        else:
            l = [("Load", self.load_server), ("Info", lambda: print("TODO"))]
            if not self.entry[3]:
                l.append(("Add…", self.add_friend))
            else:
                l.append(("Update", self.update_friend))
            self.openbubble(l)

    def add_friend(self):
        #TODO
        self.add_friend_after(self.entry[0])

    def add_friend_after(self, name):
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/exist", {"name": name}, {})
        if not ret[1]:
            ret = root.requester.requester.do_request("/client/addentity", {"name": name}, {})
            if not logcheck(ret):
                return
        self.entry[3] = name
        d = {"name": name, "hash": self.entry[1], "type": "client"}
        root.requester.requester.do_request("/client/addhash", d, {})
        self.update_friend()

    def update_friend(self):
        root = App.get_running_app().root
        text = root.requester.cur_server
        d2 = {"hash": self.entry[1], "referencetype": "surl", "reference": text}
        root.requester.requester.do_request("/client/addreference", d2, {})
        d3 = {"hash": self.entry[1], "referencetype": "sname", "reference": self.entry[0]}
        root.requester.requester.do_request("/client/addreference", d3, {})

    def load_server(self):
        ids = App.get_running_app().root.ids
        ids["convershash"].text = "{}/{}".format(self.entry[0], self.entry[1])
        ids["screenman"].current = "chats"
        ids["chatbutton"].state = "down"
        ids["serverbutton"].state = "normal"



class ChatAvailTreeNode(GridLayout):
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
        self.on_buttons(self.buttons, None)

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
        self.popup = Popup(title="Password Required", content=PwDialog(msg), size_hint=(0.9, 0.5))
        self.popup.open()

    def dismiss_popup(self):
        if self.popup:
            self.popup.dismiss()

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
            self.notify(ret)

    def send_image(self):
        self.popup = Popup(title="Load Image", content=ImageDialog(), size_hint=(0.9, 0.9))
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
        buttons = [("Send", self._send_file), ("Cancel", lambda selection: self.dismiss_popup())]
        self.popup = Popup(title="Load File", content=FileDialog(buttons=buttons), size_hint=(0.9, 0.9))
        self.popup.open()

    def _send_file(self, selectedfiles):
        self.dismiss_popup()
        if not selectedfiles or len(selectedfiles) == 0:
            return
        if self.cur_hash == "":
            return
        ret = self.requester.send_file(self.cur_hash, self.senslevel, selectedfiles[0], name=self.cur_name)
        if ret:
            self.notify(ret)


    def load_friends(self):
        lnames1 = self.requester.requester.do_request("/client/listnodeall", {"filter": "client"}, {})
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
        for centry in os.listdir(self.pathchats):
            if check_hash(centry):
                wid.add_widget(ChatAvailTreeNode(centry))

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
                print(num, "wrong type", type(num))
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
