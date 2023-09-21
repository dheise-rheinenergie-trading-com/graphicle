import json
import re
import requests
import functions as f
import config as c
import logging

log = logging.getLogger('app')


def get_categories():
    url = f'{c.cronicle["base_url"]}/api/app/get_categories/v1?api_key={c.cronicle["api_key"]}&limit={c.cronicle["limit"]}'
    try:
        res = requests.get(url, verify=False)
        data = json.loads(res.content)
    except Exception as err:
        log.error(err)
        return {}

    categories = {}
    for row in data['rows']:
        categories[row['id']] = row['title']

    return categories


def add_edge(elements, source, target, label='', edge_color=''):
    eventid = re.sub(r'.+\n.+\(([a-zA-Z0-9]+)\)$', r'\g<1>', source)
    if eventid != source:
        url = f'{c.cronicle["base_url"]}/#Schedule?sub=edit_event&id={eventid}'
        source = re.sub(r'(.+) \([a-zA-Z0-9]+\)$', r'\g<1>', source)
    else:
        eventid = ''
        url = ''
    f.add_node(elements=elements,
               path=source,
               url=url,
               hidden_notes=f'{eventid}',
               icon=f.get_icon(source),
               type=f.get_type(source))

    eventid = re.sub(r'.+\n.+\(([a-zA-Z0-9]+)\)$', r'\g<1>', target)
    if eventid != target:
        url = f'{c.cronicle["base_url"]}/#Schedule?sub=edit_event&id={eventid}'
        target = re.sub(r'(.+) \([a-zA-Z0-9]+\)$', r'\g<1>', target)
    else:
        eventid = ''
        url = ''
    f.add_node(elements=elements,
               path=target,
               url=url,
               hidden_notes=f'{eventid}',
               icon=f.get_icon(target),
               type=f.get_type(target))

    for element in elements:
        if 'source' in element['data'] and element['data']['source'] == source and element['data']['target'] == target:
            return
    elements.append({'data': {'id': f'{source}##{target}', 'source': source, 'target': target, 'label': label, 'short_label': f.shorten_label(label), 'edge_color': edge_color}})


def add_last_exit_code_status(elements, events):
    status_codes = {}
    for event in events:
        if 'last_exit_code' in event and event['plugin'] != 'workflow':
            status_codes[event['id']] = event['last_exit_code']
        else:
            log.info(f'no last_exit_code found for cronicle event "{event["title"]}" ({event["id"]})')
    for element in elements:
        if 'type' not in element['data'] or element['data']['type'] != 'Cronicle Job':
            continue
        eventid = 0
        try:
            eventid = re.sub(r'.+id=([a-zA-Z0-9]+)$', r'\g<1>', element['data']['url'])
        except Exception as err:
            log.error(err)
        symbol = '⚫ '
        if eventid in status_codes:
            if status_codes[eventid] == 0:
                symbol = '🟢 '
            if status_codes[eventid] == 1:
                symbol = '🔴 '
        element['data']['label'] = element['data']['label'].replace('\n', f'\n{symbol}')
        if element['data']['short_label']:
            element['data']['short_label'] = element['data']['short_label'].replace('\n', f'\n{symbol}')


# Befülle Datenstrukturen
def get_elements(elements=[]):
    url = f'{c.cronicle["base_url"]}/api/app/get_schedule/v1?api_key={c.cronicle["api_key"]}&limit={c.cronicle["limit"]}'
    try:
        res = requests.get(url, verify=False)
        data = json.loads(res.content)
    except Exception as err:
        log.error(err)
        return elements

    # Fehler beim Ausfuehren des API Calls
    if data['code'] == 1:
        return elements

    events = data['rows']
    categories = get_categories()
    for event in events:
        if not event['enabled'] == 1:
            continue

        category = categories[event['category']]
        notes = f'Event·ID:·{event["id"]},·Kategorie:·{category}'
        if 'notes' in event:
            notes = notes + f', weitere Infos: {event["notes"]}'
        f.add_node(elements=elements,
                   id=f'[cronicle]\n{event["title"]}',
                   path=f'[cronicle]\n{event["title"]}',
                   url=f'{c.cronicle["base_url"]}/#Schedule?sub=edit_event&id={event["id"]}',
                   hidden_notes=notes,
                   icon=f.get_icon('[cronicle]'),
                   type=f.get_type('[cronicle]'))

        # gibt es eine Success-Chain?
        if 'chain' in event and event['chain']:
            chained_event = {}
            for ce in events:
                if ce['id'] == event['chain']:
                    chained_event = ce
                    break
            add_edge(elements=elements,
                     source=f'[cronicle]\n{event["title"]} ({event["id"]})',
                     target=f'[cronicle]\n{chained_event["title"]} ({chained_event["id"]})',
                     label='OK',
                     edge_color=f.get_color('OK'))

        # gibt es eine Failure-Chain?
        if 'chain_error' in event and event['chain_error']:
            chained_event = {}
            for ce in events:
                if ce['id'] == event['chain_error']:
                    chained_event = ce
                    break
            add_edge(elements=elements,
                     source=f'[cronicle]\n{event["title"]} ({event["id"]})',
                     target=f'[cronicle]\n{chained_event["title"]} ({chained_event["id"]})',
                     label='NOK',
                     edge_color=f.get_color('NOK'))

        # nutzt der Event das Workflow Plugin?
        if event['plugin'] == 'workflow':
            try:
                subevents = event['workflow']
            except Exception as err:
                log.error(err)
                subevents = []
            for subevent in subevents:
                chained_event = {}
                for ce in events:
                    if ce['id'] == subevent['id']:
                        chained_event = ce
                        break
                if chained_event:
                    add_edge(elements=elements,
                             source=f'[cronicle]\n{event["title"]} ({event["id"]})',
                             target=f'[cronicle]\n{chained_event["title"]} ({chained_event["id"]})',
                             label='Workflow',
                             edge_color=f.get_color('workflow'))
                else:
                    log.error(f'event {event["id"]} - chained eventid {subevent["id"]} not found!')

    add_last_exit_code_status(elements, events)
    return elements
