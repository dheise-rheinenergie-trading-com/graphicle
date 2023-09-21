import logging

log = logging.getLogger('app')


def shorten_label(string, length=20):
    if not string:
        return None

    if string.startswith('[') and ']' in string:
        project = string[0:string.index(']') + 1] + '\n'
        string = string[string.index(']') + 2:]
    else:
        project = ''

    if len(string) <= length:
        return project + string
    n_2 = int(length / 2) - 3
    n_1 = length - n_2 - 3
    try:
        shorten = f'{string[:n_1]}...{string[-n_2:]}'
    except Exception as err:
        log.error(err)
        return string
    return project + shorten


def add_node(elements, path, shape='ellipse', url='', hidden_notes='', icon='#', type='default-node', id=None):
    if not id:
        id = path

    for element in elements:
        if 'id' in element['data'] and element['data']['id'] == id:
            return

    elements.append(
        {'data': {'id': id,
                  'label': path,
                  'short_label': shorten_label(path, 20),
                  'shape': shape,
                  'url': url,
                  'hidden_notes': hidden_notes,
                  'icon': icon,
                  'type': type}})


def get_icon(node_text):
    base_url = 'https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/__iconname__/default/24px.svg'

    if '[cronicle]' in node_text:
        return base_url.replace('__iconname__', 'schedule')

    return base_url.replace('__iconname__', 'folder_special')


def get_color(text):
    if 'NOK' == text:
        return 'red'
    if 'OK' == text:
        return 'lightgreen'

    return 'lightblue'


def get_type(text):
    if '[cronicle]' in text:
        return 'Cronicle Job'

    return 'default'
