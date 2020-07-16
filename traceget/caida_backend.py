import os
import time
import dill
import glob
import threading
from queue import Queue
from collections import OrderedDict

from traceget.utils import *
from traceget.logger import log


cedgar = ('cedgar@ethz.ch', 'VtDwd2^GQaGWM3PoC2')
laurent = ('lvanbever@ethz.ch', 'EPs2NF6nRiZF')
thomas = ('thomahol@ethz.ch', '1JDju69S99')

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
        time.sleep(current_retry*0.5)
        soup = get_page_soup(url, session, auth)

        if current_retry == MAX_RETRY:
            log.error("Max retries trying to get {}".format(url))
            return

    return soup

def get_available_options(url, session = None, auth=None):

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

def get_available_locations(url, session = None, auth=None):

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

def get_available_days(url, session = None, auth=None):

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

def get_available_links(url, session = None, auth=None):

    soup = get_page_soup_with_checks(url, session, auth)
    if not soup:
        log.debug("Failed to open traces/timestamps pages {}".format(url))
        return

    links = soup.find_all("a")

    download_links = {"pcap": [], "timestamps": [], "stats": []}
    for link in links:
        if link.text.endswith("pcap.gz"):
            download_links["pcap"].append((link.text, url + link.get("href")))
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
        #out_queue.put((location_info, None))
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
        time.sleep(random.uniform(0.1,0.3))
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
    #return trace_links_tree

"""
Graphical Interface Stuff
"""

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

def check_not_downloaded_traces(path_to_check, url):

    with cwd(path_to_check):
        currently_downloaded_traces = glob.glob("*")

    tmp = []
    for x in currently_downloaded_traces:
        if x.endswith(".pcap"):
            tmp.append(x+".gz")
        elif x.endswith(".pcap.gz"):
            tmp.append(x)

    currently_downloaded_traces = tmp[:]

    to_download = []
    for x in listLinks(url[1], url[2], 'UTC/'):
        for y in listLinks(x, url[2], 'pcap.gz'):
            to_download.append(y)

    to_download = [x.strip().split("/")[-1] for x in to_download]

    not_downloaded = set(to_download).difference(set(currently_downloaded_traces))
    return list(not_downloaded)

def download_missing_traces(path_to_check, url, num_cores=5):
    missing_traces = check_not_downloaded_traces(path_to_check, url)
    pool = multiprocessing.Pool(num_cores)

    url = [url]
    for name, url, auth in url:
        #print name, url, auth
        for first_link in listLinks(url, auth, 'UTC/'):
            links = listLinks(first_link, auth, 'pcap.gz')
            for link in links:
                #check if to download
                if any(link.endswith(x) for x in missing_traces):
                    pool.apply_async(download_in_path, (link, path_to_check, auth), {})

def merge_same_day_pcaps(path_to_dir="."):

    with cwd(path_to_dir):
        pool = multiprocessing.Pool(2)
        files_to_merge = [x for x in glob.glob("*") if x.endswith("UTC.anon.pcap")]

        #aggregate per day and sort per time, and dir A and B
        same_day_pcaps = {}
        for name in files_to_merge:
            day = name.split(".")[2].split("-")[0].strip()
            if same_day_pcaps.get(day, False):

                same_day_pcaps[day].append(name)
            else:
                same_day_pcaps[day] = [name]

        for element in same_day_pcaps:
            tmp = same_day_pcaps[element][:]
            same_day_pcaps[element] = sorted(tmp, key=lambda x: int(x.split("-")[-1].split(".")[0].strip()))

        #sort per dirA and B
        for day, pcaps in same_day_pcaps.iteritems():

            dirA = [x for x in pcaps if 'dirA' in x]
            dirB = [x for x in pcaps if 'dirB' in x]

            if dirA:
                linkName = dirA[0].split(".")[0].strip()
            elif dirB:
                linkName = dirB[0].split(".")[0].strip()
            else:
                continue
            if dirA:
                pool.apply_async(merge_pcaps, (dirA, "{}.dirA.{}.pcap".format(linkName, day)), {})
            if dirB:
                pool.apply_async(merge_pcaps, (dirB, "{}.dirB.{}.pcap".format(linkName, day)), {})

def main(num_cores=5, urls = []):
    pool = multiprocessing.Pool(num_cores)

    for name, url, auth in urls:
        #print name, url, auth
        os.system("mkdir -p {}".format(name))
        for first_link in listLinks(url, auth, 'UTC/')[:2]:
            print(first_link)
            links = listLinks(first_link, auth, 'pcap.gz')
            for link in links:
                print('downloading: ', link)
                pool.apply_async(download_in_path, (link, name+"/", auth), {})