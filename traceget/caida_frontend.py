import queue
import npyscreen
from appdirs import *
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

    # def activate(self):
    #    self.edit()

    def create(self):
        self.username = self.add(npyscreen.TitleText, name="Username: ")
        self.password = self.add(npyscreen.TitlePassword, name="Password: ")

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
        delta = total_time / float(100)

        self.slider.value = value
        while value < 100:
            time.sleep(delta)

            if not q.empty():
                value = 100
                self.slider.value = value
                self.slider.display()
                time.sleep(0.5)
            else:
                value = min(100, value + 1)
                self.slider.value = value
                self.slider.display()

    def activate(self):
        caida_state = self.parentApp.get_caida_base()
        username = caida_state.username

        q = queue.Queue()

        t = threading.Thread(target=self.update_slider, args=(30, q))
        t.start()

        tree = get_links_tree("https://www.caida.org/data/passive/passive_dataset_download.xml",
                              (username, caida_state.password))

        q.put(1)
        t.join()

        caida_state.links_db[username] = tree
        update_database(user_cache_dir("traceget/") + "database", caida_state.links_db)

        if not tree:
            login = self.parentApp.getForm("Login")
            login.name = "Username {} has no access to caida traces! Try again".format(username)
            self.parentApp.switchForm("Login")
        else:
            self.parentApp.switchForm("AvailableTraces")
        # available_traces = tree.keys()

    def create(self):
        self.slider = self.add(npyscreen.TitleSlider, out_of=100, name="Download Progress: ", rely=15)

    def on_cancel(self):
        self.parentApp.setNextForm(None)


class CaidaTracesDisplay(npyscreen.ActionFormV2):

    def activate(self):
        caida_state = self.parentApp.get_caida_base()
        username = caida_state.username

        if is_database(user_cache_dir("traceget/") + "database"):
            caida_state.links_db = load_database(user_cache_dir("traceget/") + "database")
        else:
            # create dir
            run_check("mkdir -p {}".format(user_cache_dir("traceget/")), True)
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
                        for i, link in enumerate(info["pcaps"]):
                            _link = _day.newChild(content=link[0].split(".anon")[0], selectable=True, expanded=False)
                            # adds real link info so its easier to get.

                            ts = [x for x in info["timestamps"] if x[0].startswith(_link.content)]
                            if ts:
                                ts = ts[0][1]
                            else:
                                ts = ""
                            stats = [x for x in info["stats"] if x[0].startswith(_link.content)]
                            if stats:
                                stats = stats[0][1]
                            else:
                                stats = ""

                            _link.real_links = {"pcap": link[1], "timestamp": ts, "stats": stats}

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
        self.wgtree = self.add(npyscreen.MLTreeMultiSelect, max_height=-2, name="Available Trace Options",
                               scroll_exit=True)


class CaidaSelectProcessingOptions(npyscreen.ActionFormV2):

    def on_cancel(self):
        self.parentApp.switchForm(None)

    def on_ok(self):

        caida_state = self.parentApp.get_caida_base()

        caida_state.root_out_path = self.root_out_path.get_value()
        caida_state.download_types = self.download_types.get_selected_objects()
        caida_state.processing_options = self.processing_options.get_selected_objects()

        # make directory
        subprocess.call("mkdir {}".format(caida_state.root_out_path), shell=True)

        if "download" in caida_state.processing_options:
            self.parentApp.switchForm("TraceDownload")
        elif "unzip" in caida_state.processing_options:
            self.parentApp.switchForm("TraceUnzip")
        elif "merge" in caida_state.processing_options:
            self.parentApp.switchForm("TraceMerge")
        else:
            self.parentApp.switchForm("End")

    def create(self):

        self.root_out_path = self.add(npyscreen.TitleFilename, name="Output Path: ", use_to_lines=True)

        self.download_types = self.add(npyscreen.TitleMultiSelect, max_height=8, value=[0],
                                       name="Select Download Types",
                                       values=["pcaps", "timestamps", "stats"], scroll_exit=True)

        self.processing_options = self.add(npyscreen.TitleMultiSelect, max_height=8, value=[0, 1, 2, 3],
                                           name="Post Processing Options",
                                           values=["download", "unzip", "merge", "clean"], scroll_exit=True)


class CaidaTraceDownload(npyscreen.Form):

    def selected_links_to_download_links(self):

        caida_state = self.parentApp.get_caida_base()
        selected_files = [x for x in caida_state.selected_links if not x.hasChildren()]
        download_links = []

        for link in selected_files:
            if link.real_links["pcap"] and "pcaps" in caida_state.download_types:
                download_links.append(link.real_links["pcap"])
            if link.real_links["timestamp"] and "timestamps" in caida_state.download_types:
                download_links.append(link.real_links["timestamp"])
            if link.real_links["stats"] and "stats" in caida_state.download_types:
                download_links.append(link.real_links["stats"])

        return download_links

    def activate(self):

        caida_state = self.parentApp.get_caida_base()
        self.download_links = self.selected_links_to_download_links()
        caida_state.download_links = self.download_links

        if len(self.download_links):
            self.slider.entry_widget.out_of = len(self.download_links)
            self.slider.display()

        result, q, pool = slider_donwload(self.download_links, caida_state.root_out_path,
                                          (caida_state.username, caida_state.password), 5)

        while True:
            if result.ready():
                break
            else:
                size = q.qsize()
                self.slider.value = size
                self.slider.display()
                time.sleep(5)

        pool.terminate()

        # check if things are downloaded as we wanted
        download_again = check_not_downloaded_files(caida_state.root_out_path, self.download_links)
        while download_again:

            self.name = "Downloading Traces Again...."
            self.display()

            if len(self.download_links):
                self.slider.entry_widget.out_of = len(download_again)
                self.slider.display()

            result, q, pool = slider_donwload(download_again, caida_state.root_out_path,
                                              (caida_state.username, caida_state.password), 5)

            while True:
                if result.ready():
                    break
                else:
                    size = q.qsize()
                    self.slider.value = size
                    self.slider.display()
                    time.sleep(5)

            pool.terminate()
            download_again = check_not_downloaded_files(caida_state.root_out_path, self.download_links)

        if "unzip" in caida_state.processing_options:
            self.parentApp.switchForm("TraceUnzip")
        elif "merge" in caida_state.processing_options:
            self.parentApp.switchForm("TraceMerge")
        else:
            self.parentApp.switchForm("End")

    def create(self):
        self.slider = self.add(npyscreen.TitleSlider, out_of=100, name="Download Traces Progress: ", rely=15)


class CaidaTraceUnzip(npyscreen.Form):

    def activate(self):

        caida_state = self.parentApp.get_caida_base()
        caida_state.to_unzip = get_zipped_files(caida_state.root_out_path, ".gz")

        if len(caida_state.to_unzip):
            self.slider.entry_widget.out_of = len(caida_state.to_unzip)
            self.slider.display()

        result, q, pool = slider_unzip(caida_state.to_unzip, caida_state.root_out_path, 6)

        while True:
            if result.ready():
                break
            else:
                size = q.qsize()
                self.slider.value = size
                self.slider.display()
                time.sleep(5)

        pool.terminate()

        if "merge" in caida_state.processing_options:
            self.parentApp.switchForm("TraceMerge")
        else:
            self.parentApp.switchForm("End")

    def create(self):
        self.slider = self.add(npyscreen.TitleSlider, out_of=100, name="Unzipping Files Progress ", rely=15)


class CaidaTraceMerge(npyscreen.Form):

    def activate(self):
        caida_state = self.parentApp.get_caida_base()

        # merge files
        clean = False
        if "clean" in caida_state.processing_options:
            clean = True

        merge_same_day_files(caida_state.root_out_path, "pcap", clean)
        merge_same_day_files(caida_state.root_out_path, "times", clean)

        self.parentApp.switchForm("End")

    def create(self):
        pass


class CaidaEnd(npyscreen.ActionFormV2):

    def create(self):
        pass

    def on_ok(self):
        self.parentApp.switchForm(None)

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

        # Download, uncompress, and merge
        self.addForm("TraceDownload", CaidaTraceDownload, name="Downloading Traces")
        self.addForm("TraceUnzip", CaidaTraceUnzip, name="Unzipping Traces")
        self.addForm("TraceMerge", CaidaTraceMerge, name="Merging Traces")
        self.addForm("End", CaidaEnd, name="Done!")

    def get_caida_base(self):
        return self.caida_base


def main():
    npyscreen.wrapper(CaidaApp().run())


if __name__ == "__main__":
    main()
