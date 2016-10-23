
import logging
import os

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
                self.closebubble()


class PwDialog(FloatLayout):
    def pw(self):
        return self.ids["pwfield"].text
    def __init__(self, msg, *args, **kwargs):
        self.msg = None
        super().__init__(*args, **kwargs)
        self.ids["pwfield"].text = msg
        #self.ids["msg"] = msg


class PopupNew(Popup):
    def __init__(self, *args, **kwargs):
        if "content" in kwargs:
            kwargs["content"].parent_popup = self
        super().__init__(*args, **kwargs)
        self.size_hint = (0.9, 0.9)
        self.on_content(self.content, None)

    def on_content(self, instance, value):
        if self.content:
            self.content.parent_popup = self

class DeleteDialog(FloatLayout):
    buttons = ListProperty()
    message = StringProperty()
    parent_popup = None
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
            b.bind(on_press=lambda x:self.call(func))
            self.ids["buttonlist"].add_widget(b)

    def on_message(self, instance, value):
        if "deletemsg" not in self.ids:
            return
        self.ids["deletemsg"].text = instance

    def call(self, func):
        self.popup_parent.dismiss()
        func()

class ListDialog(FloatLayout):
    buttons = ListProperty()
    entries = ListProperty()
    parent_popup = None

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
            but = Button(text=name)
            but.bind(on_press=lambda butinstance: self.call(func))
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

    def call(self, func):
        if self.ids["viewlist"].selected_node:
            arg = self.ids["viewlist"].selected_node.message
        else:
            arg = None
        if not func(arg):
            self.parent_popup.dismiss()


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
            b.bind(on_press=lambda butinstance: self.call(func))
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

    def call(self, func):
        if not func(self.ids["selectedfile"].selection, self.ids["nameinput"].text):
            self.parent_popup.dismiss()

class NameDialogAdd(FloatLayout):
    nameproposal = StringProperty("")
    func = None
    parent_popup = None
    def __init__(self, func, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = func
        self.ids["newname"].text = self.nameproposal

    def ok(self):
        self.parent_popup.dismiss()
        self.func(self.ids["newname"].text)

    def cancel(self):
        self.parent_popup.dismiss()

class NameDialog(ListDialog):
    nameproposal = StringProperty("")
    func = None
    parent_popup = None
    def __init__(self, func, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func = func
        self.buttons = [("Select", self.return_selected), ("Add new", self.add_entity), ("Close", lambda x: self.return_selected(None))]

    @staticmethod
    def load_entities():
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/listnodenames", {}, {})
        if not logcheck(ret):
            return None
        return map(lambda entry: (entry, (1, 1, 1, 1)), ret[2].get("items"))

    @classmethod
    def create(cls, func, *args, **kwargs):
        ret = cls.load_entities()
        if not ret:
            return None
        return cls(func, *args, entries=ret, **kwargs)

    def add_entity(self, ignored=None):
        dia = NameDialogAdd(self.add_entity_afterask, nameproposal=self.nameproposal)
        PopupNew(title="Add", content=dia, size_hint=(0.8, 0.4)).open()
        return True

    def add_entity_afterask(self, name):
        root = App.get_running_app().root
        ret = root.requester.requester.do_request("/client/addentity", {"name": name}, {})
        if not logcheck(ret):
            return True
        self.entries = self.load_entities()
        return True

    def return_selected(self, name):
        self.func(name)
