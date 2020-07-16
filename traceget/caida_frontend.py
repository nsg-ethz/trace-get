import npyscreen
import ipdb
import traceback
import queue
from traceget.caida_backend import *

class CaidaDataBase(object):

    def __init__(self):
        self.username = ""
        self.password = ""
        self.selected_links = ""

class MainForm(npyscreen.ActionForm):

    def create(self):
        self.parentApp.setNextForm("Login")

class CaidaLogin(npyscreen.ActionForm):

    def activate(self):
        self.edit()

    def create(self):
        self.username = self.add(npyscreen.TitleText, name="Username: ", value=cedgar[0])
        self.password = self.add(npyscreen.TitlePassword, name="Password: ", value=cedgar[1])

    def on_ok(self):

        caida_db = self.parentApp.get_caida_base()
        caida_db.username = self.username.value
        caida_db.password = self.password.value
        self.parentApp.setNextForm("AvailableTraces")

    def on_cancel(self):
        self.parentApp.setNextForm(None)

class CaidaLoadLinks(npyscreen.ActionForm):

    def update_slider(self, total_time=30, q=None):

        value = 0
        delta = total_time/float(100)

        self.slider.value = value
        while value < 100:
            time.sleep(delta)

            if not q.empty():
                value = 100
                self.slider.value = value
                self.slider.display()
                time.sleep(0.5)
            else:
                value = min(100, value+1)
                self.slider.value = value
                self.slider.display()

    def activate(self):
        caida_state = self.parentApp.get_caida_base()
        username = caida_state.username

        q = queue.Queue()

        t = threading.Thread(target=self.update_slider, args=(30,q))
        t.start()

        tree = get_links_tree("https://www.caida.org/data/passive/passive_dataset_download.xml",
                              (username, caida_state.password))

        q.put(1)
        t.join()

        caida_state.links_db[username] = tree
        update_database("db.pickle", caida_state.links_db)

        if not tree:
            login = self.parentApp.getForm("Login")
            login.name = "Username {} has no access to caida traces! Try again".format(username)
            self.parentApp.switchForm("Login")
        else:
            self.parentApp.switchForm("AvailableTraces")
        #available_traces = tree.keys()

    def create(self):
        self.slider  = self.add(npyscreen.TitleSlider, out_of=100, name = "Download Progress: ")

    def on_cancel(self):
        self.parentApp.setNextForm(None)


class CaidaTracesDisplay(npyscreen.ActionFormV2):

    def activate(self):
        caida_state = self.parentApp.get_caida_base()
        username = caida_state.username

        if is_database("db.pickle"):
            caida_state.links_db = load_database("db.pickle")
        else:
            caida_state.links_db = {}

        # try to find our links.. otherwise we need to load
        if caida_state.links_db.get(username):

            trace_links = caida_state.links_db.get(username)

            treedata = npyscreen.NPSTreeData(content='Root', selectable=True, ignoreRoot=True)

            for years, locations in trace_links.items():
                _year = treedata.newChild(content=years, selectable=True, expanded=False)
                for location, days in locations.items():
                    _location = _year.newChild(content=location, selectable=True, expanded=False)
                    for day, info in days.items():
                        _day = _location.newChild(content=day, selectable=True, expanded=False)
                        for file_type, links in info.items():
                            _type = _day.newChild(content=file_type, selectable=True, expanded=False)
                            for link in links:
                                _type.newChild(content=link[0], selectable=True, expanded=False)
            self.wgtree.values = treedata
            self.edit()

        else:
            self.parentApp.switchForm("LoadLinks")


    def on_ok(self):
        caida_state = self.parentApp.get_caida_base()
        caida_state.selected_links = self.wgtree.get_selected_objects()
        self.parentApp.switchForm("ProcessingOptions")

    def on_cancel(self):
        self.parentApp.switchForm(None)


    def create(self):
        self.wgtree = self.add(npyscreen.MLTreeMultiSelect, max_height=-2, name="Available Trace Options", scroll_exit = True)


class CaidaSelectProcessingOptions(npyscreen.ActionFormV2):

    def on_cancel(self):
        self.parentApp.switchForm(None)

    def on_ok(self):
        self.parentApp.switchForm(None)


    def create(self):
        pass


class CaidaAvailableTraces(npyscreen.ActionForm):
    def activate(self):
        caida_state = self.parentApp.get_caida_base()
        username = caida_state.username

        if is_database("db.pickle"):
            caida_state.links_db = load_database("db.pickle")
        else:
            caida_state.links_db = {}

        # try to find our links.. otherwise we need to load
        if caida_state.links_db.get(username):
            available_traces = caida_state.links_db.get(username).keys()
            self.available_options.values = list(available_traces)
            self.edit()

        else:
            self.parentApp.switchForm("LoadLinks")


    def create(self):

        self.available_options = self.add(npyscreen.TitleMultiSelect, max_height=-2, name="Available Trace Options", scroll_exit = True)


    def on_cancel(self):
        self.parentApp.switchForm(None)

class CaidaApp(npyscreen.NPSAppManaged):
    def onStart(self):
        self.caida_base = CaidaDataBase()
        self.addForm("MAIN", MainForm, name="")
        self.addForm("Login", CaidaLogin, name="Caida Login Page")
        self.addForm("AvailableTraces", CaidaTracesDisplay, name="The CAIDA Anonymized Internet Traces Data Access")
        self.addForm("LoadLinks", CaidaLoadLinks, name="Loading Links from Caida....")
        self.addForm("ProcessingOptions", CaidaSelectProcessingOptions, name="Caida Porcessing Options")


    def get_caida_base(self):
        return self.caida_base

if __name__ == "__main__":
    npyscreen.wrapper(CaidaApp().run())

