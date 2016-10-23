#! /usr/bin/env python3

import io
import os
import shutil

from kivy.app import App
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.uix.floatlayout import FloatLayout

from simplescn.tools import logcheck

from chatkivy.dialogs import FileDialog, PopupNew, UseBubble, DeleteDialog, ListDialog, NameDialog
from chatscn import messagebuffer, simplelock


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
        buttons = [("Download", self.download_afterask), ("Cancel", lambda x, y: None)]
        dia = FileDialog(buttons=buttons, dirselect=True)
        PopupNew(title="Download", content=dia).open()

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
        buttonlist = [("Delete", self.remove_afterask), ("Cancel", lambda: None)]
        msg = 'Really delete download offer for file: "{}"?'.format(self.indict.get("name"))
        dia = DeleteDialog(message=msg, buttons=buttonlist)
        PopupNew(title="Confirm Deletion", content=dia, size_hint=(0.9, 0.5)).open()

    def remove_afterask(self, instance):
        root = App.get_running_app().root
        certhash = self.indict.get("certhash")
        fileid = self.indict.get("fileid")
        messagebuffer.get("certhash", {}).pop(fileid)
        fjspath = os.path.join(root.pathchats, certhash, fileid)
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
        elif indict["type"] == "image":
            #self.height = 100
            l = io.BytesIO(bytes(indict["image"], "utf-8"))
            img = Image()
            img.texture = CoreImage(source=l, size_hint=size, pos_hint=pos)
            self.add_widget(img)
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
            self.openbubble([("Load", self.load_friend), ("Rename", self.rename), ("Delete", self.delete_friend)])

    def rename(self):
        self.closebubble()
        dia = NameDialog.create(self.rename_call)
        if not dia:
            return
        PopupNew(title="Rename", content=dia).open()

    def rename_call(self, name):
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/renameentity", {"name": self.text, "newname": name, "merge":True}, {})
        if not logcheck(ret):
            return
        root.load_friends()

    def load_friend(self):
        self.closebubble()
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/listhashes", {"name": self.text, "filter": "client"}, {})
        if not logcheck(ret):
            return
        buttons = [("Load", self.load_hash), ("Close", lambda x: None)]
        newlist = map(lambda entry: (entry[0], (1, 0, 0, 1) if entry[4] == "valid" else (1, 1, 1, 1)), ret[2]["items"])
        dia = ListDialog(entries=newlist, buttons=buttons)

        PopupNew(title="Hashes", content=dia).open()


    def load_hash(self, selected):
        if not selected:
            return
        root = App.get_running_app().root
        root.ids["convershash"].text = "{}/{}".format(self.text, selected)
        root.ids["screenman"].current = "chats"
        root.ids["chatbutton"].state = "down"
        root.ids["serverbutton"].state = "normal"

    def delete_friend(self):
        buttonlist = [("Delete", self.delete_friend_afterask), ("Cancel", lambda: None)]
        msg = 'Really delete friend: "{}"?'.format(self.text)
        dia = DeleteDialog(message=msg, buttons=buttonlist)
        PopupNew(title="Confirm Deletion", content=dia, size_hint=(0.9, 0.5)).open()

    def delete_friend_afterask(self):
        root = App.get_running_app().root
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
            l = []
            if not self.entry[3]:
                l.append(("Load", self.load_server_direct))
                l.append(("Add…", self.add_friend))
            else:
                l.append(("Load", self.load_server))
                l.append(("Update", self.update_friend))
            self.openbubble(l)

    def add_friend(self):
        dia = NameDialog.create(self.add_friend_after, nameproposal=self.entry[0])
        if not dia:
            return
        PopupNew(title="Rename", content=dia).open()

    def add_friend_after(self, name):
        root = App.get_running_app().root
        self.entry[3] = name
        d = {"name": name, "hash": self.entry[1], "type": "client"}
        root.requester.requester.do_request("/client/addhash", d, {})
        self.update_friend()

    def update_friend(self):
        root = App.get_running_app().root
        text = root.requester.cur_server
        d2 = {"hash": self.entry[1], "reftype": "surl", "reference": text}
        ret = root.requester.requester.do_request("/client/addreference", d2, {})
        logcheck(ret)
        d3 = {"hash": self.entry[1], "reftype": "sname", "reference": self.entry[0]}
        ret = root.requester.requester.do_request("/client/addreference", d3, {})
        logcheck(ret)

    def load_server(self):
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/listhashes", {"name": self.text, "filter": "client"}, {})
        if not logcheck(ret):
            return
        if len(ret[2]["items"]) <= 1:
            self.load_server_direct()
            return
        newlist = map(lambda entry: (entry[0], (1, 0, 0, 1) if entry[4] == "valid" else (0, 0, 0, 1)), ret[2]["items"])
        buttons = [("Load", self.load_server_direct)]
        dia = ListDialog(entries=newlist, buttons=buttons)
        PopupNew(title="Hashes", content=dia).open()

    def load_server_direct(self, _hash=None):
        if not _hash:
            _hash = self.entry[1]
        root = App.get_running_app().root
        root.ids["convershash"].text = "{}/{}".format(self.entry[0], _hash)
        root.ids["screenman"].current = "chats"
        root.ids["chatbutton"].state = "down"
        root.ids["serverbutton"].state = "normal"

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
        if not self.entry[0]:
            root = App.get_running_app().root
            root.set_namehash(self.entry[1])
            root.ids["convershash"].text = self.entry[1]
        if self._oldstate == "normal":
            self._oldstate = self.state
            if self.entry[0]:
                self.open_dia()
            return super().on_press()
        self._oldstate = self.state
        if not self.entry[0]:
            if not self.bubble:
                l = [("Clear", lambda: self.clear_chats(self.entry[1])), \
                      ("Clear private", lambda: self.clear_chats_private(self.entry[1]))]
                self.openbubble(l)
            else:
                self.closebubble()
        else:
            self.open_dia()
        return super().on_press()

    def open_dia(self):
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/listhashes", {"name": self.entry[0]}, {})
        if not logcheck(ret):
            return
        hashes = map(lambda x: (x[0], (0, 0, 0, 1)), ret[2].get("items"))
        buttons = [("Select", self.load_selected), ("Clear", self.clear_chats), ("Close", lambda sel: None)]
        dia = ListDialog(entries=hashes, buttons=buttons)
        PopupNew(title="Select hash", content=dia).open()

    def clear_chats(self, selected):
        if not selected:
            return
        root = App.get_running_app().root
        with simplelock:
            shutil.rmtree(os.path.join(root.pathchats, selected), ignore_errors=True)
            if selected in messagebuffer:
                del messagebuffer[selected]
        root.load_conversation()

    def clear_chats_private(self, selected):
        if not selected:
            return
        with simplelock:
            if selected in messagebuffer:
                del messagebuffer[selected]
        root = App.get_running_app().root
        root.load_conversation()

    def load_selected(self, selected):
        if not selected:
            return
        root = App.get_running_app().root
        root.set_namehash(selected)
        root.ids["convershash"].text = selected

    def load_direct(self):
        root = App.get_running_app().root
        root.set_namehash(self.entry[1])
        root.ids["convershash"].text = self.entry[1]
