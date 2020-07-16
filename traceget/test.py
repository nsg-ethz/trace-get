from traceget.caida_backend import *
from traceget.utils import *

url1 = 'https://www.caida.org/data/passive/passive_dataset_download.xml'
url2 = "https://data.caida.org/datasets/passive-2012/"
url3 = "https://data.caida.org/datasets/passive-2011/equinix-chicago/"
url4 = "https://data.caida.org/datasets/passive-2011/equinix-chicago/20110217-130000.UTC/"
# listLinks(url1, laurent)
# get_available_options(url1, None)
# get_available_locations(url2, laurent)
# get_available_locations(url2, None)
# get_available_days(url3, laurent)
# get_available_pcaps(url4, laurent)
# get_available_timestamps(url4, laurent)


tree = get_links_tree(url1, laurent)



# print(tree)