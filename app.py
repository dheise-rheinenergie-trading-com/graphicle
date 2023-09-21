#!/bin/env python3

from dash.dependencies import Input, Output, State
from dash import dcc, html
from datetime import datetime, timedelta
import config as c
import cronicle
import dash
import dash_cytoscape as cyto
import inspect
import logging
import re
import urllib3
import urllib.parse
import uuid

'''
URL: https://ret-goto/dash/
Optionale Parameter:
- search=[Suchbegriff1,Suchbegriff%20Nummer%202]
- filter=[Filter1,Filter%20Nummer%202]
- selected=[Begriff1,Begriff%20Nummer%202]
- opacity=[0-1]
- export=[jpg]
- layout=[klay,cose,...]
- viewmode=[full,readonly]
- title=Bla-Bla-Text
'''

logging.basicConfig(encoding='UTF-8', level=c.log['level'])
log = logging.getLogger('app')

urllib3.disable_warnings()

animate = c.dash['animate']
animationDuration = c.dash['animate_duration']
cytoscape = None
all_sessions = {}

# Dash App
cyto.load_extra_layouts()
app = dash.Dash(inspect.stack()[0][3], title=c.webserver['title'], url_base_pathname=c.webserver['context_root'])


# get userspecific settings from session storage
def get_session_data(session_id):
    global all_sessions

    if not session_id:
        return {}

    if session_id not in all_sessions:
        all_sessions[session_id] = {}
        all_sessions[session_id]['elements'] = []
        all_sessions[session_id]['selected_nodes'] = []
        all_sessions[session_id]['last_opacity'] = 0.5
        all_sessions[session_id]['layout'] = 'klay'
        all_sessions[session_id]['search_string'] = ''
        all_sessions[session_id]['filter_string'] = ''
        all_sessions[session_id]['options'] = []
        all_sessions[session_id]['viewmode'] = 'full'
        all_sessions[session_id]['title'] = ''
    all_sessions[session_id]['expires_at'] = datetime.now() + timedelta(hours=24)

    # delete expired sessions
    for id in list(all_sessions.keys()):
        if all_sessions[id]['expires_at'] < datetime.now():
            all_sessions.pop(id)

    return all_sessions[session_id]


# create all nodes and edges
def get_elements(session_id):
    session_data = get_session_data(session_id)
    session_data['elements'] = []
    session_data['elements'] = cronicle.get_elements(elements=session_data['elements'])

    # return all elements if no filter is set
    if len(session_data['filter_string']) == 0:
        return session_data['elements']

    # backup all elements before filtering
    session_data['unfiltered_elements'] = session_data['elements']

    # filter nodes
    filter = session_data['filter_string'].split(',')
    deleted_ids = []
    # delete unwanted nodes
    for element in list(session_data['elements']):
        # skip element if it is not a node
        if 'id' not in element['data']:
            continue
        delete = True
        for f in filter:
            regex = re.compile(f)
            if regex.search(element['data']['id'].lower()):
                delete = False
        if delete:
            deleted_ids.append(element['data']['id'])
            try:
                session_data['elements'].remove(element)
            except Exception as err:
                log.error(err)

    # delete orphaned edges
    for element in list(session_data['elements']):
        # skip element id it is not an edge
        if 'source' not in element['data']:
            continue
        if element['data']['source'] in deleted_ids or element['data']['target'] in deleted_ids:
            try:
                session_data['elements'].remove(element)
            except Exception as err:
                log.error(err)

    return session_data['elements']


# Callbacks - set layout
@app.callback(Output('cytoscape', 'layout'),
              [State('session-id', 'data'),
              Input('dropdown-layout', 'value')])
def callback_modified_layout(session_id, new_layout):
    global animate, animationDuration

    session_data = get_session_data(session_id)
    session_data['layout'] = new_layout

    return {'name': new_layout, 'animate': animate, 'animationDuration': animationDuration, 'nodeDimensionsIncludeLabels': 'true'}


# Callbacks - refresh nodes and edges after searching/filtering
@app.callback(Output('cytoscape', 'elements'),
              [State('session-id', 'data'),
              Input('input-filter', 'value'),
              Input('button-refresh', 'n_clicks')])
def callback_modified_modulelist(session_id, filter, button_refresh):
    session_data = get_session_data(session_id)
    session_data['filter_string'] = filter
    return get_elements(session_id)


# Callbacks - generate styleshees
@app.callback(Output('cytoscape', 'stylesheet'),
              [State('session-id', 'data'),
              Input('cytoscape', 'selectedNodeData'),
              Input('input-search', 'value'),
              Input('slider-opacity', 'value'),
              Input('checklist-options', 'value'),
              Input('button-refresh', 'n_clicks')])
def callback_refresh_cytoscape(session_id, selectedNodeData, search, opacity, selected_options, button_refresh):
    session_data = get_session_data(session_id)

    session_data['search_string'] = search
    session_data['options'] = selected_options
    session_data['last_opacity'] = opacity
    session_data['selected_nodes'] = selectedNodeData

    if len(session_data['elements']) == 0:
        get_elements(session_id)

    # generate styles for cytograph
    style1 = generate_stylesheet(session_id)
    style2 = generate_stylesheet_selected_nodes(session_id)

    # combine both styles together
    return style1 + style2


# Callback - load settings from url or after a reset
@app.callback([Output('dropdown-layout', 'value'),
              Output('input-search', 'value'),
              Output('input-filter', 'value'),
              Output('slider-opacity', 'value'),
              Output('checklist-options', 'value'),
              Output('cytoscape', 'selectedNodeData'),
              Output('menu', 'style'),
              Output('title', 'children')],
              [State('session-id', 'data'),
              Input('button-reset', 'n_clicks'),
              Input('url', 'search')])
def callback_load_settings(session_id, n_clicks_reset, url):
    ctx = dash.callback_context
    input_id = ctx.triggered[0]['prop_id'].split('.')[0]
    session_data = get_session_data(session_id)

    if input_id == 'button-reset':
        all_sessions[session_id]['selected_nodes'] = []
        all_sessions[session_id]['last_opacity'] = 0.5
        all_sessions[session_id]['layout'] = 'klay'
        all_sessions[session_id]['search_string'] = ''
        all_sessions[session_id]['filter_string'] = ''
        all_sessions[session_id]['options'] = []
        all_sessions[session_id]['viewmode'] = 'full'

    if input_id == 'url':
        parameter = url.replace('?', '').split('&')
        for p in parameter:
            if '=' in p:
                key_value = p.split('=')
                key = key_value[0].lower()
                value = key_value[1]

                if key == 'search':
                    session_data['search_string'] = urllib.parse.unquote(value)
                if key == 'filter':
                    session_data['filter_string'] = urllib.parse.unquote(value)
                if key == 'opacity':
                    session_data['last_opacity'] = float(value)
                if key == 'layout':
                    session_data['layout'] = value.lower()
                if key == 'viewmode':
                    session_data['viewmode'] = value.lower()
                if key == 'selected':
                    session_data['preselected_nodes'] = value.split(',')
                if key == 'title':
                    session_data['title'] = urllib.parse.unquote(value)

    menu_style = {'flex': '0 0 150px', 'padding': '5px', 'margin': '5px', 'border': '1px solid lightgray'}
    if session_data['viewmode'] == 'readonly':
        menu_style = {'display': 'none'}

    return session_data['layout'], session_data['search_string'], session_data['filter_string'], session_data['last_opacity'], session_data['options'], session_data['selected_nodes'], menu_style, session_data['title']


# Callback - export jpg
@app.callback(Output('cytoscape', 'generateImage'),
              [State('session-id', 'data'),
              Input('button-export', 'n_clicks'),
              Input('url', 'search')])
def callback_clicked_export_button(session_id, n_clicks, url):
    ctx = dash.callback_context
    if ctx.triggered:
        input_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if input_id == 'button-export' or (input_id == 'url' and 'export=jpg' in url):
            return {'type': 'jpg', 'action': 'download'}

    return {}


# Callback - show toolip
@app.callback(Output('tooltip', 'children'),
              [State('session-id', 'data'),
              Input('cytoscape', 'mouseoverNodeData')])
def callback_hovered_node(session_id, data):
    session_data = get_session_data(session_id)

    if not data:
        return html.Div()

    if session_data['selected_nodes'] and len(session_data['selected_nodes']) > 0:
        found = False
        for selected in session_data['selected_nodes']:
            if selected['id'] == data['id']:
                found = True
                data = selected
        if not found:
            return html.Div()

    div = html.Div([
        html.Span(f'{data["label"]}', style={'font-weight': 'bold'}), html.Br(),
        html.Span(f'Type: {data["type"]}'), html.Br(),
        html.Span('Link: '), html.A(data['url'], href=data['url'], target='_blank'), html.Br(),
        html.Span('Notes: {}'.format(data['hidden_notes']))
    ], id='fff', style={'min-height': '100px', 'padding-left': '100px', 'background-size': '80px', 'background-image': f'url("{data["icon"]}")', 'background-repeat': 'no-repeat'})
    return div


def getLayout():
    global animate, animationDuration, cytoscape

    session_id = str(uuid.uuid4())
    session_data = get_session_data(session_id)

    cytoscape = cyto.Cytoscape(id='cytoscape', elements=session_data['elements'], boxSelectionEnabled=True, responsive=True, minZoom=0.1, maxZoom=2, autoRefreshLayout=True,
                               layout={'name': 'klay', 'animate': animate, 'animationDuration': animationDuration},
                               style={'width': '100%', 'height': '85%'})
    containerDiv = html.Div([html.Div(html.H1('', id='title'), style={'position': 'absolute', 'left': '30px'}),
                            dcc.Location(id='url', refresh=False),
                            html.Div([cytoscape,
                                     html.Div([], id='tooltip', style={'padding': '5px', 'margin': '5px', 'min-height': '100px', 'border-top': '1px solid lightgray'})],
                                     style={'flex': '1 1 auto', 'padding': '5px', 'margin': '5px', 'border': '1px solid lightgray'}),

                            html.Div([dcc.Store(id='session-id', data=session_id),
                                     html.Span('Search:'), html.Br(),
                                     dcc.Input(id='input-search', type='text', value='', debounce=True, style={'width': '95%'}), html.Br(),

                                     html.Span('Filter:'), html.Br(),
                                     dcc.Input(id='input-filter', type='text', value='', debounce=True, style={'width': '95%'}), html.Br(),

                                     html.Span('Graph Layout:'), html.Br(),
                                     dcc.Dropdown(id='dropdown-layout', value=session_data['layout'], clearable=False,
                                                  options=[{'label': 'breadthfirst', 'value': 'breadthfirst'},
                                                           {'label': 'circle', 'value': 'circle'},
                                                           {'label': 'concentric', 'value': 'concentric'},
                                                           {'label': 'cola', 'value': 'cola'},
                                                           {'label': 'cose', 'value': 'cose'},
                                                           {'label': 'dagre', 'value': 'dagre'},
                                                           {'label': 'euler', 'value': 'euler'},
                                                           {'label': 'grid', 'value': 'grid'},
                                                           {'label': 'klay', 'value': 'klay'},
                                                           {'label': 'random', 'value': 'random'},
                                                           {'label': 'spread', 'value': 'spread'}]),

                                     html.Span('Opacity:'), html.Br(),
                                     dcc.Slider(id='slider-opacity', min=0, max=1, step=0.05, value=session_data['last_opacity'], marks=None), html.Br(), html.Hr(),
                                     html.Span('Options:'), html.Br(),
                                     dcc.Checklist(id='checklist-options', options=[{'value': 'shorten-labels', 'label': 'Shorten labels'}], value=[], labelStyle={'display': 'block'}), html.Br(), html.Hr(),

                                     html.Button('Refresh', id='button-refresh'), html.Br(), html.Br(),
                                     html.Button('Export JPG', id='button-export'), html.Br(), html.Br(),
                                     html.Button('Reset', id='button-reset', n_clicks=0)],
                                     id='menu', style={'flex': '0 0 150px', 'padding': '5px', 'margin': '5px', 'border': '1px solid lightgray'})],
                            style={'display': 'flex', 'font-family': 'Verdana', 'font-size': '10pt', 'height': '97vh'})
    return containerDiv


def generate_stylesheet(session_id):
    session_data = get_session_data(session_id)

    nodes_list = session_data['elements']
    search = session_data['search_string']
    opacity = session_data['last_opacity']
    options = session_data['options']

    if 'shorten-labels' in options:
        label = 'data(short_label)'
    else:
        label = 'data(label)'

    stylesheet = [
        {
            'selector': 'node',
            'style': {
                'label': label,
                'shape': 'data(shape)',
                'background-size': '95%',
                'background-image': 'data(icon)',
                'border-style': 'none',
                'opacity': opacity,
                'font-size': 12,
                'font-family': 'Verdana',
                'text-wrap': 'wrap',
                'text-valign': 'bottom'
            }
        },
        {
            'selector': 'edge',
            'style': {
                'label': label,
                'target-arrow-shape': 'triangle',
                'arrow-scale': 2,
                'curve-style': 'unbundled-bezier',
                'opacity': opacity,
                'font-size': 12,
                'text-wrap': 'wrap',
            }
        },
    ]

    # no nodes selected
    if not nodes_list or len(nodes_list) == 0:
        return stylesheet

    # highlight all nodes with matching search pattern
    for node in nodes_list:
        if 'source' not in node['data'] and len(search) > 0:
            found = False
            search_strings = search.lower().split(',')
            for s in search_strings:
                regex = re.compile(s)
                if regex.search(node['data']['id'].lower()) or regex.search(node['data']['hidden_notes'].lower()):
                    found = True
                    break

            if found:
                stylesheet.append({
                    'selector': f'node[id = "{node["data"]["id"]}"]',
                    'style': {
                        'border-style': 'solid',
                        'border-color': 'purple',
                        'border-width': 4,
                        'border-opacity': 1,
                        'opacity': 1,
                        'z-index': 9999,
                        'font-weight': 'bold'
                    }
                })
    return stylesheet


# generate specific stylesheets for all selected nodes and their edges
def generate_stylesheet_selected_nodes(session_id):
    session_data = get_session_data(session_id)

    if 'preselected_nodes' in session_data:
        for node in session_data['preselected_nodes']:
            if len(node) > 0:
                for e in session_data['elements']:
                    if node in e['data']['id']:
                        session_data['selected_nodes'].append(e['data'])

    nodes_list = session_data['selected_nodes']
    stylesheet = []

    # no nodes selected
    if not nodes_list or len(nodes_list) == 0:
        return stylesheet

    for node in nodes_list:
        # highlight selected node
        stylesheet.append({
            'selector': f'node[id="{node["id"]}"]',
            'style': {
                'background-color': 'lightblue',
                'opacity': '1',
                'border-style': 'solid',
                'border-color': 'orange',
                'border-width': '4',
                'border-opacity': '1',
                'text-opacity': '1',
                'z-index': 9999,
                'font-weight': 'bold'
            }
        })
        # highlight all direct edges from and to the selected node
        stylesheet.append({
            'selector': f'edge[source="{node["id"]}"], edge[target="{node["id"]}"]',
            'style': {
                'target-arrow-color': 'data(edge_color)',
                'line-color': 'data(edge_color)',
                'opacity': '1',
                'text-opacity': '1'
            }
        })

        # highlight all direct connected nodes
        for element in session_data['elements']:
            if 'source' in element['data'] and (node['id'] == element['data']['source'] or node['id'] == element['data']['target']):
                stylesheet.append({
                    'selector': 'node[id="{}"], node[id="{}"]'.format(element['data']['source'], element['data']['target']),
                    'style': {
                        'background-color': 'lightblue',
                        'opacity': '1',
                        'z-index': 9999,
                        'font-weight': 'bold'
                    }
                })

    return stylesheet


# start Dash App
app.layout = getLayout
app.run_server(debug=True, host='0.0.0.0', port=c.webserver['port'])
