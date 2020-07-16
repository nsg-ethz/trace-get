from contextlib import contextmanager
from functools import wraps
import os
import subprocess
import multiprocessing
import time, random
import requests
import ipdb

from bs4 import BeautifulSoup

from traceget.logger import log



"""
Page Interaction
"""

def download_in_path(url, path, auth):
    time.sleep(random.randint(1,20))
    print("Start Downloading: ", url)
    cmd = 'wget --quiet --user {} --password {} {}'.format(auth[0], auth[1],url)
    call_in_path(cmd, path)

def is_authorization_required(soup):
    return "401" in (soup.find("title").text).lower()

def is_service_unavailable(soup):
    return "503" in (soup.find("title").text).lower()

def get_page_soup(url, session = None, auth=None):

    if session:
        page = session.get(url).text

    elif auth:
        page = requests.get(url, auth=requests.auth.HTTPBasicAuth(*auth)).text
    else:
        page = requests.get(url).text

    soup = BeautifulSoup(page, 'html.parser')
    return soup

"""
Decorators
"""

def time_profiler(function):
    def wrapper(*args, **kwargs):
        now = time.time()
        r = function(*args, **kwargs)
        print("Function {0} was executed in {1} seconds".format(function.__name__, time.time() - now))
        return r
    return wrapper


"""
Command execution support
"""

@contextmanager
def cwd(path):
    """
    Conext that changes current path for some piece of code and returns to the previous
    path once the we leave the context.
    Args:
        path: path to switch to
    Returns:
    """
    oldpwd = os.getcwd()
    os.chdir(os.path.expanduser(path))
    try:
        yield
    finally:
        os.chdir(oldpwd)

def run_cmd(cmd, shell=True):
    log.debug(cmd)
    subprocess.call(cmd, shell=shell)


def run_check(cmd, shell=True):
    log.debug(cmd)
    return subprocess.check_output(cmd, shell=shell)


def call_in_path(cmd, path, quiet=True):
    with cwd(path):
        if not quiet:
            print(cmd, path)
            return
        run_cmd(cmd, shell=True)


def call_in_path_and_write_out(cmd, path, outfile, quiet=True):
    with cwd(path):
        if not quiet:
            print(cmd, path)
            return
        with open(outfile, "w") as f:
            subprocess.run(cmd, shell=True, stdout=f, stderr=f)


def find_files_in_dir(dir, regex=".*pcap"):
    """
    Args:
        dir:
        pattern:
    Returns:
    """
    with cwd(dir):
        out = run_check('find "$PWD" -type f -regex "%s"' % regex).split("\n")
        out = [x.strip() for x in out if x]
    return out


"""
util functions
"""
def unzip_pcaps(path_to_unzip, extension = "pcap.gz", num_cores=24):
    with cwd(path_to_unzip):
        files_to_unzip = [x for x in glob.glob("*") if x.endswith(extension)]

    pool = multiprocessing.Pool(num_cores)
    for pcap in files_to_unzip:
        cmd = "gunzip {}".format(pcap)
        pool.apply_async(call_in_path, (cmd, path_to_unzip), {})

def merge_pcaps(global_dir, output_file):
    """
    Merges all the pcap from a given directory and saves them at output_file
    Args:
        burst_dir: Directory where we can find all the pcap files
        output_file: Output pcap file name

    Returns: None

    """
    cmd_base = "mergecap -F libpcap -w %s " % (output_file) + " %s"

    with cwd(global_dir):
        print(os.getcwd())
        out = subprocess.check_output("find . -type f -name '*pcap'", shell=True)
        out = out.replace("\n", " ")
        cmd = cmd_base % out
        subprocess.call(cmd, shell=True)


def merge_pcaps(pcap_files, output_file):
    """
    Merges a list of pcap files into one
    Args:
        pcap_files: list of pcaps
        output_file: output pcap file name

    Returns: None

    """

    file_format = 'libpcap'

    cmd_base = "mergecap -F %s -w %s " % (file_format, output_file) + " %s"
    cmd = cmd_base % " ".join(pcap_files)
    run_cmd(cmd)


def merge_pcaps_dir(dir, output_file, regex= ".*pcap"):
    """
    Merges all the pcap files in a directory
    Args:
        dir: directory to merge
        output_file: pcap output file
        regex: regular expression for the types of files to merge, in theory pcaps

    Returns:

    """
    pcap_files = find_files_in_dir(dir, regex=regex)
    merge_pcaps(pcap_files, output_file)

