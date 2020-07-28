import threading
from collections import OrderedDict
from queue import Queue

import dill

from traceget.logger import log
from traceget.utils import *

MAX_RETRY = 10

"""
Caida Links Database
"""


def load_database(file_name):
    if not is_database(file_name):
        return {}
    else:
        return dill.load(open(file_name, "rb"))


def update_database(file_name, new_db):
    dill.dump(new_db, open(file_name, "wb"))


def is_database(file_name):
    return os.path.exists(file_name)


"""
Get Page Links
"""


def get_page_soup_with_checks(url, session=None, auth=None):
    current_retry = 0
    soup = get_page_soup(url, session, auth)

    if is_authorization_required(soup):
        log.debug("Unauthorized access to {}".format(url))
        return

    while is_service_unavailable(soup):
        current_retry += 1
        time.sleep(current_retry * 0.5)
        soup = get_page_soup(url, session, auth)

        if current_retry == MAX_RETRY:
            log.error("Max retries trying to get {}".format(url))
            return

    return soup


def get_available_options(url, session=None, auth=None):
    soup = get_page_soup_with_checks(url, session, auth)
    if soup == -1:
        log.error("Failed to open caida main page {}".format(url))
        return

    quote = soup.find("blockquote")
    available_traces = []

    for trace in quote.find_all("a"):

        if "report" not in trace.text:
            trace_name = trace.text
            trace_link = trace.get("href")
            available_traces.append((trace_name, trace_link))

    return available_traces


def get_available_locations(url, session=None, auth=None):
    soup = get_page_soup_with_checks(url, session, auth)
    if not soup:
        log.debug("Failed to open equinix-location pages {}".format(url))
        return

    links = soup.find_all("a")

    link_locations = []
    for link_location in links:
        if "equinix" in link_location.text:
            link_locations.append((link_location.text, url + "/" + link_location.get("href")))

    return link_locations


def get_available_days(url, session=None, auth=None):
    soup = get_page_soup_with_checks(url, session, auth)
    if not soup:
        log.debug("Failed to open days pages {}".format(url))
        return

    links = soup.find_all("a")

    day_links = []
    for link in links:
        if link.text.endswith("UTC/"):
            day_links.append((link.text, url + link.get("href")))

    return day_links


def get_available_links(url, session=None, auth=None):
    soup = get_page_soup_with_checks(url, session, auth)
    if not soup:
        log.debug("Failed to open traces/timestamps pages {}".format(url))
        return

    links = soup.find_all("a")

    download_links = {"pcaps": [], "timestamps": [], "stats": []}
    for link in links:
        if link.text.endswith("pcap.gz"):
            download_links["pcaps"].append((link.text, url + link.get("href")))
        elif link.text.endswith("times.gz"):
            download_links["timestamps"].append((link.text, url + link.get("href")))
        elif link.text.endswith("pcap.stats"):
            download_links["stats"].append((link.text, url + link.get("href")))

    return download_links


def get_links_tree_worker(location_info, auth=None, out_queue=None):
    session = requests.session()
    session.auth = auth
    trace_links_tree = OrderedDict()

    locations = get_available_locations(location_info[1], session, auth)

    if not locations:
        # out_queue.put((location_info, None))
        return

    for location_name, location_link in locations:
        trace_links_tree[location_name] = OrderedDict()
        days = get_available_days(location_link, session, auth)

        if not days:
            continue

        for day_name, day_link in days:
            download_links = get_available_links(day_link, session, auth)
            if download_links:
                try:
                    trace_links_tree[location_name][day_name] = download_links.copy()
                except:
                    print("\n\n\n")
                    print(locations, days, download_links)

    out_queue.put((location_info, trace_links_tree))
    return


def get_links_tree(main_url, auth=None):
    now = time.time()

    trace_links_tree = OrderedDict()
    options = get_available_options(main_url, auth=None)

    queue = Queue()
    threads = []

    for option_name, option_link in options:
        t = threading.Thread(target=get_links_tree_worker, args=((option_name, option_link), auth, queue))
        time.sleep(random.uniform(0.1, 0.3))
        threads.append(t)
        t.start()

    [x.join() for x in threads]

    out = []
    while not queue.empty():
        out.append(queue.get())
        queue.task_done()

    for option in options:
        for _option in out:
            if _option[0] == option:
                trace_links_tree[option[0]] = _option[1]

    print("runtime: ", time.time() - now)
    return trace_links_tree
    # return trace_links_tree


"""
Download Stuff
"""


def slider_donwload(list_of_links, path, auth, processes=5):
    pool = multiprocessing.Pool(processes)
    manager = multiprocessing.Manager()
    q = manager.Queue()

    args = []
    for link in list_of_links:
        args.append((link, path + "/", auth, q))

    result = pool.map_async(download_in_path_with_queue, args)

    return result, q, pool


def check_not_downloaded_files(path_to_check, files_to_download):
    with cwd(path_to_check):
        currently_downloaded_files = glob.glob("*")

    tmp = []
    for x in currently_downloaded_files:
        if x.endswith(".pcap"):
            tmp.append(x + ".gz")
        elif x.endswith(".pcap.gz"):
            tmp.append(x)
        elif x.endswith(".times"):
            tmp.append(x + ".gz")
        elif x.endswith("times.gz"):
            tmp.append(x)
        else:
            tmp.append(x)

    currently_downloaded_traces = tmp[:]

    not_downloaded = []

    for file in files_to_download:
        if any(x in file for x in currently_downloaded_traces):
            pass
        else:
            not_downloaded.append(file)

    return not_downloaded


def rename_pcaps(preamble):
    files_to_rename = [x for x in glob.glob("*") if not x.endswith("anon.pcap")]
    for f in files_to_rename:
        current_name = f
        day = current_name.split("-")[0].strip()
        t = current_name.split("_")[1]
        direction = current_name.split("_")[-1].split(".")[0].strip()
        new_name = "{}.{}.{}-{}.UTC.anon.pcap".format(preamble, direction, day, t)
        cmd = "mv {} {}".format(current_name, new_name)
        call_in_path(cmd, ".")


"""
Uncompressing
"""


def call_in_path_queue(args):
    cmd, path, q = args
    call_in_path(cmd, path)
    q.put(1)


def slider_unzip(files_to_unzip, path, processes=5):
    pool = multiprocessing.Pool(processes)
    manager = multiprocessing.Manager()
    q = manager.Queue()

    args = []
    for file_to_unzip in files_to_unzip:
        args.append(("gunzip {}".format(file_to_unzip), path, q))

    result = pool.map_async(call_in_path_queue, args)

    return result, q, pool


"""
Merging
"""


def merge_times(times_files, output_file, clean=False):
    """
    Merges a list of pcap files into one
    Args:
        pcap_files: list of pcaps
        output_file: output pcap file name

    Returns: None

    """

    cmd_base = "cat %s > %s"
    cmd = cmd_base % (" ".join(times_files), output_file)
    run_cmd(cmd)

    # remove pcap files
    if clean:
        cmd = "rm " + " ".join(times_files)
        run_cmd(cmd)


def merge_same_day_files(path_to_dir=".", merge_type="pcap", clean=False):
    same_day_files = {}
    _FUNCTION = None
    if merge_type == "pcap":
        _FUNCTION = merge_pcaps_from_list
    elif merge_type == "times":
        _FUNCTION = merge_times

    with cwd(path_to_dir):
        pool = multiprocessing.Pool(1)
        files_to_merge = [x for x in glob.glob("*") if x.endswith("UTC.anon.{}".format(merge_type))]

        # aggregate per day and sort per time, and dir A and B
        for name in files_to_merge:
            day = name.split(".")[2].split("-")[0].strip()
            if same_day_files.get(day, False):

                same_day_files[day].append(name)
            else:
                same_day_files[day] = [name]

        for element in same_day_files:
            tmp = same_day_files[element][:]
            same_day_files[element] = sorted(tmp, key=lambda x: int(x.split("-")[-1].split(".")[0].strip()))

        # sort per dirA and B
        for day, files in same_day_files.items():

            dirA = [x for x in files if 'dirA' in x]
            dirB = [x for x in files if 'dirB' in x]

            if dirA:
                linkName = dirA[0].split(".")[0].strip()
            elif dirB:
                linkName = dirB[0].split(".")[0].strip()
            else:
                continue
            if dirA:
                #pool.apply_async(_FUNCTION, (dirA, "{}.dirA.{}.{}".format(linkName, day, merge_type), clean), {})
                _FUNCTION(dirA, "{}.dirA.{}.{}".format(linkName, day, merge_type), clean)
                #pool.apply_async(_FUNCTION, (dirA, "{}.dirA.{}.{}".format(linkName, day, merge_type), clean), {})
            if dirB:
                #pool.apply_async(_FUNCTION, (dirB, "{}.dirB.{}.{}".format(linkName, day, merge_type), clean), {})
                _FUNCTION(dirB, "{}.dirB.{}.{}".format(linkName, day, merge_type), clean)

    pool.close()
    pool.join()
    pool.terminate()
