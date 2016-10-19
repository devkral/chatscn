
import logging
import os
import threading

from simplescn.tools import logcheck

from kivy.uix.popup import Popup
from kivy.properties import ListProperty, StringProperty, BooleanProperty
from kivy.uix.bubble import BubbleButton, Bubble
from kivy.uix.treeview import TreeViewLabel
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.app import App

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
    def touch_grab(self, widget, touch):
        touch.grab(self)
    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.close_on_pos(touch.pos)
        return True


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
                print("collide", bubble.pos, pos)
                self.closebubble()


class PwDialog(FloatLayout):
    msg = None
    def __init__(self, *args, **kwargs):
        self.msg = None
        super().__init__(*args, **kwargs)
        #self.ids["msg"] = msg


class PopupNew(Popup):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.size_hint = (0.9, 0.9)
    def on_dismiss(self):
        App.get_running_app().root.popup = None
        return False

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

class NameDialogAdd(FloatLayout):
    nameproposal = StringProperty()
    event = None
    selected = None
    def __init__(self, *args, **kwargs):
        super.__init__(*args, **kwargs)
        self.event = threading.Event()
        self.event.clear()

    def ok(self):
        self.selected = self.ids["nameproposal"].text
        self.dismiss()
        self.event.set()
    def cancel(self):
        self.selected = None
        self.dismiss()
        self.event.set()

    def wait_selected(self):
        self.event.wait()
        return self.selected

class NameDialog(ListDialog):
    event = None
    selected = None
    nameproposal = StringProperty()
    def __init__(self, *args, **kwargs):
        super.__init__(*args, **kwargs)
        self.event = threading.Event()
        self.event.clear()
        self.buttons = [("Select", self.return_selected), ("Add new", self.add_entity), ("Close", lambda x: self.return_selected(None))]

    @staticmethod
    def load_entities():
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/listnodenames", {}, {})
        if not logcheck(ret):
            return None
        return map(lambda entry: (entry, (1, 0, 0, 1)), ret[2].get("items"))
    @classmethod
    def create(cls, *args, **kwargs):
        ret = cls.load_entities()
        if not ret:
            return None
        return cls(*args, entries=ret, **kwargs)


    def add_entity(self, ignored):
        dia = NameDialogAdd(nameproposal=self.nameproposal)
        popup = PopupNew(title="Add", content=dia)
        popup.open()
        name = popup.wait_selected()
        if not name:
            return
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/addentity", {"name": name}, {})
        if not logcheck(ret):
            return
        self.entries = self.load_entities()

    def return_selected(self, name):
        self.selected = name
        root = App.get_running_app().root
        self.event.set()
        root.dismiss_popup()

    def wait_selected(self):
        self.event.wait()
        return self.selected
