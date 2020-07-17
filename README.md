CAIDA TRACES DOWNLOADER
=======================

Tool to easily download, uncompress and merge caida pcap files, timestamps and statistics.

To install this tool just run the install script:

```
./install.sh
```

Once the tool is installed you can run it by typing `traceget` in your terminal.

```
traceget
```

First you will be promted with a `user` and `password` screen. Use your caida credentials to access your traces.


## Navigation

1. Use arrows and TAB to move around.
2. Use space to select or unselect boxes.
3. Use `>` to unfold menus and `<` to fold menus.

## Walkthrough

1. Login page: Introduce your the mail and password you used to register at caida. Press `Ok` to login.

<p align="center">
<img src="images/login.png" title="Login Page">
<p/>

2. If it is the first time you login in the app will automatically download all the links for traces you have access
to. This might take several seconds:

<p align="center">
<img src="images/database.png" title="Downloading all the available traces for the user">
<p/>


3. Select the traces you want to download. The traces are displayed in a hierarchical manner: `Year->Link->Day->Minutes`. You
can navigate the menu and select from entire years (using space bar) or you can expand menus using `>` to select more specific traces.

<p align="center">
<img src="images/traces.png" title="Select the traces you want to download by (year, link, day, minute)">
<p/>


4. Finally you have to choose some downloading options:
    1. Select the path were you want the files to be downloaded.
    2. Select if you want to download pcaps, timestamps and/or stats.
    3. Select if you wan to only download, or also unzip and merge same day traces.

<p align="center">
<img src="images/options.png" title="Select your options (path, types of files, and postprocessing)">
<p/>


5. Finally the download will start. If you selected the unzip and merge options, once the download is over that will start.

<p align="center">
<img src="images/downloading.png" title="Downloading Page">
<p/>