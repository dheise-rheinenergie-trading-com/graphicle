# graphicle
Ploty based diagram for the task scheduler "cronicle"

![image](https://github.com/dheise-rheinenergie-trading-com/graphicle/assets/73586581/e33be328-47c8-44a5-b31b-b57d9808ee76)

## features
- interactive diagram (nodes can be moved, clicked...)
- search und highlight nodes
- filter nodes
- regex support for search and filter
- shortcuts to the cronicle events
- green and red icons showing the last run status
- jpg export
- all options url-configurable (GET parameter see below)

## installation
- clone repo
- make sure your python is up to date (tested with 3.11)
- install required python modules (python3 -m pip install -r requirements.txt)

## configuration
- open config.py
- edit the base url for your cronicle installation
- set your cronicle api key (generate a new one without any additional privileges)
- set your desired port and context root for the webserver

## running
- start the webserver with python3 ./app.py
- open graphicle in your browser 

## optional GET parameter
optional parameter:
- search=[word1,filter%20number%202]
- filter=[filter1,filter%20number%202]
- selected=[word1,word2%20number%202]
- opacity=[0-1]
- export=[jpg]
- layout=[klay,cose,...]
- viewmode=[full,readonly]
- title=some%20title%20text
