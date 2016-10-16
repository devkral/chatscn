
import kivy
kivy.require('1.9.1')

import threading
import os
import io
import json
import logging
from __init__ import messagebuffer

from kivy.app import App
#from kivy.uix.pagelayout import PageLayout
from kivy.uix.treeview import TreeView, TreeViewNode, TreeViewLabel
from kivy.uix.gridlayout import GridLayout
#from kivy.uix.boxlayout import BoxLayout
#from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.properties import ListProperty, StringProperty, BooleanProperty
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

class UseBubble(object):
    bubble = None
    callbackid = None
    def openbubble(self, buttonfunclist, data=None):
        if self.bubble:
            logging.error("Bubble already called")
            return
        self.bubble = Bubble(height=30, width=10, pos=self.to_window(self.x, self.y+30), size_hint=(None, None))
        for text, func in buttonfunclist:
            button = BubbleButton(text=text, height=30)
            self.bubble.width += 10 + len(text)*10
            self.call(button, func, data)
            self.bubble.add_widget(button)
        root = App.get_running_app().root
        #self.get_root_window().add_widget(self.bubble, root.canvas)
        root.add_widget(self.bubble)
        self.callbackid = root.fbind("on_touch_down", self.touch_grab)
        #root.fbind(pos=)
    def touch_grab(self, widget, touch):
        touch.grab(self)
    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.close_on_pos(touch.pos)

    def closebubble(self):
        if self.bubble:
            #self.get_root_window().remove_widget(self.bubble)
            root = App.get_running_app().root
            root.unbind_uid("on_touch_down", self.callbackid)
            root.clear_widgets([self.bubble])
            self.bubble = None
    def on_parent(self, instance, value):
        self.closebubble()

    def call(self, button, funccall, data):
        def _call(instance):
            self.closebubble()
            if data:
                return funccall(data)
            else:
                return funccall()
        button.bind(on_press=_call)

    def close_on_pos(self, pos):
        bubble = self.bubble
        if bubble:
            if not bubble.collide_point(*pos) and not self.collide_point(*pos):
                self.closebubble()


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

def createListButton(text, func, viewlist):
    def newfunc(instance):
        if viewlist.selected_node:
            func(viewlist.selected_node.message)
        else:
            func(None)
    but = Button(text=text)
    but.bind(on_press=newfunc)
    return but

class ListDialog(FloatLayout):
    buttons = ListProperty()
    entries = ListProperty()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_entries(self.entries, None)
        self.on_buttons(self.buttons, None)

    def on_buttons(self, instance, value):
        if "buttonlist" not in self.ids:
            return
        self.ids["buttonlist"].clear_widgets()
        for elem in self.buttons:
            name, func = elem
            but = createListButton(name, func, self.ids["viewlist"])
            self.ids["buttonlist"].add_widget(but)

    def on_entries(self, instance, value):
        if "viewlist" not in self.ids:
            return
        viewlist = self.ids["viewlist"]
        viewlist.clear_widgets()
        for elem in self.entries:
            lab = TreeViewLabel(text=elem[0])
            lab.color = elem[1]
            if len(elem) == 3:
                lab.message = elem[2]
            else:
                lab.message = elem[0]
            viewlist.add_node(lab)

class FileEntry(Button):
    indict = None
    def __init__(self,indict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.indict = indict
        if indict["owner"]:
            self.text = "Remove File: {}".format(indict["filepath"])
            self.bind(on_press=self.remove)
        else:
            self.text = "Download File: {}".format(indict.get("name", ""))
            self.bind(on_press=self.download)

    def download(self, instance):
        root = App.get_running_app().root
        buttons = [("Download", self.download_afterask), ("Cancel", lambda x, y: root.dismiss_popup)]
        dia = FileDialog(buttons=buttons, dirselect=True)
        root.popup = PopupNew(title="Download", content=dia, size_hint=(0.9, 0.5))
        root.popup.open()

    def download_afterask(self, selection, name):
        if not selection or not os.path.exist(selection):
            return
        if os.path.isdir(selection):
            newpath = os.path.join(selection, name)
        else:
            newpath = os.path.join(os.path.basedir(selection), name)
        root = App.get_running_app().root
        resp = root.do_requestdo("/send_file/{}".format(self.indict.get("fileid")), {}, {})
        if not resp:
            return
        retlen = resp.headers.get("Content-Length", "")
        if retlen.isdecimal():
            with open(newpath, "wb") as wob:
                wob.write(resp.read(int(retlen)))

    def remove(self, instance):
        root = App.get_running_app().root
        buttonlist = [("Delete", self.remove_afterask), ("Cancel", root.dismiss_popup)]
        msg = 'Really delete download offer for file: "{}"?'.format(self.indict.get("name"))
        dia = DeleteDialog(message=msg, buttons=buttonlist)
        root.popup = PopupNew(title="Confirm Deletion", content=dia, size_hint=(0.9, 0.5))
        root.popup.open()

    def remove_afterask(self, instance):
        certhash = self.indict.get("certhash")
        fileid = self.indict.get("fileid")
        messagebuffer.get("certhash", {}).pop(fileid)
        fjspath = os.path.join(self.basedir, certhash, fileid)
        if os.path.exists(fjspath):
            try:
                os.remove(fjspath)
            except:
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
            self.add_widget(FileEntry(indict, size_hint=size, pos_hint=pos))
        else:
            raise

class FriendTreeNode(UseBubble, Button):
    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = name
        #self.add_widget(Label(text=self.entry[4]))

    def on_press(self):
        if self.bubble:
            self.closebubble()
        else:
            self.openbubble([("Load", self.load_friend), ("Rename", lambda:print("TODO")), ("Delete", self.delete_friend)])

    def load_friend(self):
        self.closebubble()
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/listhashes", {"name": self.text, "filter": "client"}, {})
        if not logcheck(ret):
            return
        buttons = [("Load", self.load_hash), ("Close", lambda x: root.dismiss_popup())]
        newlist = map(lambda entry: (entry[0], (1, 0, 0, 1) if entry[4] == "valid" else (0, 0, 0, 1)), ret[2]["items"])
        dia = ListDialog(entries=newlist, buttons=buttons)

        root.popup = PopupNew(title="Hashes", content=dia, size_hint=(0.9, 0.5))
        root.popup.open()


    def load_hash(self, selected):
        if not selected:
            return
        root = App.get_running_app().root
        root.dismiss_popup()
        root.ids["convershash"].text = "{}/{}".format(self.text, selected)
        root.ids["screenman"].current = "chats"
        root.ids["chatbutton"].state = "down"
        root.ids["serverbutton"].state = "normal"

    def delete_friend(self):
        root = App.get_running_app().root
        buttonlist = [("Delete", self.delete_friend_afterask), ("Cancel", root.dismiss_popup)]
        msg = 'Really delete friend: "{}"?'.format(self.text)
        dia = DeleteDialog(message=msg, buttons=buttonlist)
        root.popup = PopupNew(title="Confirm Deletion", content=dia, size_hint=(0.9, 0.5))
        root.popup.open()

    def delete_friend_afterask(self):
        root = App.get_running_app().root
        root.dismiss_popup()
        ret = root.requester.requester.do_request("/client/delentity", {"name":self.text})
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



class ChatAvailTreeNode(UseBubble, ToggleButton):
    entry = None
    _oldstate = "normal"
    def __init__(self, certhash,localname=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if localname:
            self.entry = (localname, None)
            self.text = localname
        else:
            self.entry = (localname, certhash)
            self.text = certhash

    def on_press(self):
        if self._oldstate == "normal":
            self._oldstate = self.state
            if self.entry[0]:
                self.open_dia()
            return super().on_press()
        self._oldstate = self.state
        if not self.entry[0]:
            if not self.bubble:
                l = [("Clear", lambda x: self.clear_chats(self.entry[1])), \
                      ("Clear private", lambda x: self.clear_chats_private(self.entry[1]))]
                self.openbubble(l)
            else:
                self.closebubble()
        else:
            self.open_dia()
        return super().on_press()


    #def on_state(self, instance, value):
    #    if not self.entry[0]:
    #        return self.load_direct()
    #    self.open_dia()

    def open_dia(self):
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/listhashes", {"name": self.entry[0]}, {})
        if not logcheck(ret):
            return
        hashes = map(lambda x: (x[0], (0, 0, 0, 1)), ret[2].get("items"))
        buttons = [("Select", self.load_selected), ("Clear", self.clear_chats), ("Close", lambda sel: root.dismiss_popup())]
        dia = ListDialog(entries=hashes, buttons=buttons)
        root.popup = PopupNew(title="Select hash", content=dia, size_hint=(0.9, 0.5))
        root.popup.open()

    def clear_chats(self, selected):
        if not selected:
            return
        #TODO
        pass

    def clear_chats_private(self, selected):
        if not selected:
            return
        #TODO
        pass

    def load_selected(self, selected):
        if not selected:
            return
        root = App.get_running_app().root
        root.dismiss_popup()
        root.ids["convershash"].text = selected

    def load_direct(self):
        root = App.get_running_app().root
        root.ids["convershash"].text = self.entry[1]


class FileDialog(FloatLayout):
    buttons = ListProperty()
    label = StringProperty("Name")
    text = StringProperty("")
    dirselect = BooleanProperty(False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_buttons(self.buttons, None)
        self.on_label(self.label, None)
        self.on_text(self.text, None)
        self.on_dirselect(self.dirselect, None)

    def on_dirselect(self, instance, value):
        if "selectedfile" not in self.ids:
            return
        self.ids["selectedfile"].dirselect = instance

    def on_label(self, instance, value):
        if "namelabel" not in self.ids:
            return
        self.ids["namelabel"].text = instance

    def on_text(self, instance, value):
        if "nameinput" not in self.ids:
            return
        self.ids["nameinput"].text = instance

    def on_buttons(self, instance, value):
        if "selectedfile" not in self.ids:
            return
        self.ids["buttonlist"].clear_widgets()
        for elem in self.buttons:
            name, func = elem
            b = Button(text=name)
            b.bind(on_press=lambda butinstance: func(self.ids["selectedfile"].selection, self.ids["nameinput"]))
            self.ids["buttonlist"].add_widget(b)

    def select(self, selection):
        if "nameinput" not in self.ids:
            return
        if not selection or len(selection) <= 0:
            return
        if os.path.isdir(selection[0]):
            return
        nameinput = self.ids["nameinput"]
        nameinput.text = os.path.basename(selection[0])

class ChatView(FloatLayout):
    pass
class PwDialog(FloatLayout):
    msg = None
    def __init__(self, *args, **kwargs):
        self.msg = None
        super().__init__(*args, **kwargs)
        #self.ids["msg"] = msg


class PopupNew(Popup):
    def on_dismiss(self):
        App.get_running_app().root.popup = None
        return False
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
