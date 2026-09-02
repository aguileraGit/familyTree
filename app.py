import os
import re
import uuid
from functools import wraps
from typing import Optional, Dict, Any

import networkx as nx
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pocketbase import PocketBase

app = Flask(__name__)
CORS(app)

pb = PocketBase('https://pocketbase.tail32217.ts.net')

HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
DEFAULT_GROUP_COLOR = '#6c757d'


def _load_git_sha() -> str:
    """Resolve a short git SHA to display for build/deploy verification.

    Reads a GIT_SHA file baked into the image at build time (see the
    Dockerfile — it curls GitHub's API for the latest commit on the
    deployed branch, since Portainer's git-stack build does not preserve
    a .git directory to run `git rev-parse` against). Falls back to
    'unknown' if the file is missing, so a build-step issue never breaks
    the app — it just shows nothing useful yet.
    """
    sha_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GIT_SHA')
    try:
        with open(sha_file) as f:
            return f.read().strip() or 'unknown'
    except Exception:
        return 'unknown'


GIT_SHA = _load_git_sha()

# ─────────────────────────────────────────────
# PocketBase helpers
# ─────────────────────────────────────────────

def get_tree_by_access_code(access_code: str) -> Optional[Dict]:
    try:
        print(f"[DEBUG] Looking up access_code: '{access_code}'")
        result = pb.collection('trees').get_full_list(
            query_params={'filter': f'access_code="{access_code}"'}
        )
        print(f"[DEBUG] PocketBase returned {len(result)} record(s)")
        if result:
            return result[0]
        return None
    except Exception as e:
        print(f"[DEBUG] Exception during lookup: {e}")
        return None


def get_people_for_tree(tree_uuid: str) -> list:
    try:
        return pb.collection('people').get_full_list(
            query_params={'filter': f'tree_id="{tree_uuid}"'}
        )
    except Exception:
        return []


def normalize_group(value) -> Dict[str, Any]:
    """Return a {'name': ..., 'color': ...} dict for a family_groups entry.

    Handles both the legacy plain-string format ("Hinson Family") and the
    current {'name': ..., 'color': ...} format, so old trees keep working
    without a migration step. Old entries are normalized on read; they get
    rewritten to the new format the next time that group is saved (renamed
    or recolored).
    """
    if isinstance(value, dict):
        return {'name': value.get('name', ''), 'color': value.get('color')}
    return {'name': value, 'color': None}


def get_tree_family_groups(tree_record) -> Dict[str, Dict[str, Any]]:
    try:
        groups = getattr(tree_record, 'family_groups', None)
        if not isinstance(groups, dict):
            return {}
        return {gid: normalize_group(value) for gid, value in groups.items()}
    except Exception:
        return {}


def save_tree_family_groups(tree_record_id: str, groups: Dict) -> bool:
    try:
        pb.collection('trees').update(tree_record_id, {'family_groups': groups})
        return True
    except Exception as e:
        print(f"[DEBUG] Failed to save family groups: {e}")
        return False


def record_to_person(record) -> Dict[str, Any]:
    raw_groups = getattr(record, 'family_groups', None) or []
    if isinstance(raw_groups, list):
        family_groups = [g for g in raw_groups if isinstance(g, str)]
    else:
        family_groups = []
    return {
        'first_name':     record.first_name,
        'last_name':      record.last_name,
        'middle_name':    getattr(record, 'middle_name', None) or None,
        'nick_name':      getattr(record, 'nick_name', None) or None,
        'sex':            record.sex,
        'family_groups':  family_groups,
        'father_id':      record.father_id or None,
        'mother_id':      record.mother_id or None,
        'birthday':       record.birthday or None,
        'place_of_birth': record.place_of_birth or None,
        'current_location': record.current_location or None,
        'pos_x':          getattr(record, 'pos_x', None),
        'pos_y':          getattr(record, 'pos_y', None),
    }


def build_graph(people_records: list) -> nx.DiGraph:
    graph = nx.DiGraph()
    for record in people_records:
        graph.add_node(record.person_uuid, **record_to_person(record))
    for record in people_records:
        if record.father_id and graph.has_node(record.father_id):
            graph.add_edge(record.father_id, record.person_uuid, relation='father')
        if record.mother_id and graph.has_node(record.mother_id):
            graph.add_edge(record.mother_id, record.person_uuid, relation='mother')
    return graph


def get_pb_record_by_person_uuid(person_uuid: str, tree_uuid: str):
    try:
        filter_str = f'person_uuid="{person_uuid}" && tree_id="{tree_uuid}"'
        print(f"[DEBUG] get_pb_record filter: {filter_str}")
        return pb.collection('people').get_first_list_item(filter_str)
    except Exception as e:
        print(f"[DEBUG] get_pb_record exception: {e}")
        return None


# ─────────────────────────────────────────────
# Auth middleware
# ─────────────────────────────────────────────

def require_tree(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        access_code = request.headers.get('X-Access-Code')
        print(f"[DEBUG] require_tree: access_code={access_code}")
        if not access_code:
            return jsonify({'success': False, 'error': 'Missing X-Access-Code header'}), 401
        tree = get_tree_by_access_code(access_code)
        if not tree:
            return jsonify({'success': False, 'error': 'Invalid access code'}), 403
        kwargs['tree_uuid'] = tree.tree_uuid
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', git_sha=GIT_SHA)


@app.route('/landing', methods=['GET'])
def landing():
    return render_template('landing.html')


# ─────────────────────────────────────────────
# Tree endpoint
# ─────────────────────────────────────────────

@app.route('/api/tree/enter', methods=['POST'])
def enter_tree():
    data = request.json
    access_code = data.get('access_code')
    if not access_code:
        return jsonify({'success': False, 'error': 'access_code is required'}), 400
    tree = get_tree_by_access_code(access_code)
    if not tree:
        return jsonify({'success': False, 'error': 'Invalid access code'}), 403
    return jsonify({
        'success': True,
        'tree': {
            'tree_uuid':     tree.tree_uuid,
            'name':          tree.name,
            'description':   getattr(tree, 'description', '') or '',
            'family_groups': get_tree_family_groups(tree)
        }
    }), 200


# ─────────────────────────────────────────────
# Family Group endpoints
# ─────────────────────────────────────────────

@app.route('/api/familygroups', methods=['GET'])
@require_tree
def get_family_groups(tree_uuid=None):
    access_code = request.headers.get('X-Access-Code')
    tree = get_tree_by_access_code(access_code)
    groups = get_tree_family_groups(tree)
    return jsonify({'success': True, 'family_groups': groups}), 200


@app.route('/api/familygroup', methods=['POST'])
@require_tree
def create_family_group(tree_uuid=None):
    print(f"[DEBUG] create_family_group called, tree_uuid={tree_uuid}")
    access_code = request.headers.get('X-Access-Code')
    tree = get_tree_by_access_code(access_code)
    data = request.json
    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': 'name is required'}), 400
    color = data.get('color') or DEFAULT_GROUP_COLOR
    if not HEX_COLOR_RE.match(color):
        return jsonify({'success': False, 'error': 'color must be a hex value like #00429d'}), 400
    groups = get_tree_family_groups(tree)
    group_uuid = str(uuid.uuid4())
    groups[group_uuid] = {'name': data['name'], 'color': color}
    if save_tree_family_groups(tree.id, groups):
        return jsonify({
            'success': True,
            'group_uuid': group_uuid,
            'name': data['name'],
            'color': color,
            'family_groups': groups
        }), 201
    return jsonify({'success': False, 'error': 'Failed to save group'}), 500


@app.route('/api/familygroup/<path:group_uuid>', methods=['PUT'])
@require_tree
def update_family_group(group_uuid, tree_uuid=None):
    access_code = request.headers.get('X-Access-Code')
    tree = get_tree_by_access_code(access_code)
    data = request.json or {}
    groups = get_tree_family_groups(tree)
    if group_uuid not in groups:
        return jsonify({'success': False, 'error': 'Group not found'}), 404

    existing = groups[group_uuid]
    name  = data.get('name', existing['name'])
    color = data.get('color', existing['color']) or DEFAULT_GROUP_COLOR
    if not name:
        return jsonify({'success': False, 'error': 'name is required'}), 400
    if not HEX_COLOR_RE.match(color):
        return jsonify({'success': False, 'error': 'color must be a hex value like #00429d'}), 400

    groups[group_uuid] = {'name': name, 'color': color}
    if save_tree_family_groups(tree.id, groups):
        return jsonify({'success': True, 'family_groups': groups}), 200
    return jsonify({'success': False, 'error': 'Failed to save group'}), 500


@app.route('/api/familygroup/<path:group_uuid>', methods=['DELETE'])
@require_tree
def delete_family_group(group_uuid, tree_uuid=None):
    access_code = request.headers.get('X-Access-Code')
    tree = get_tree_by_access_code(access_code)
    groups = get_tree_family_groups(tree)
    if group_uuid not in groups:
        return jsonify({'success': False, 'error': 'Group not found'}), 404
    del groups[group_uuid]
    if save_tree_family_groups(tree.id, groups):
        return jsonify({'success': True, 'family_groups': groups}), 200
    return jsonify({'success': False, 'error': 'Failed to delete group'}), 500


# ─────────────────────────────────────────────
# Person endpoints
# ─────────────────────────────────────────────

@app.route('/api/person', methods=['POST'])
@require_tree
def add_person(tree_uuid=None):
    data = request.json
    try:
        father_id = data.get('father_id')
        mother_id = data.get('mother_id')
        family_groups = data.get('family_groups') or []
        person_uuid = str(uuid.uuid4())
        sex = data['sex'].lower()
        pb.collection('people').create({
            'tree_id':        tree_uuid,
            'person_uuid':    person_uuid,
            'first_name':     data['first_name'],
            'last_name':      data['last_name'],
            'middle_name':    data.get('middle_name', ''),
            'nick_name':      data.get('nick_name', ''),
            'sex':            sex[0].upper(),
            'family_groups':  family_groups,
            'father_id':      father_id or '',
            'mother_id':      mother_id or '',
            'birthday':       data.get('birthday', ''),
            'place_of_birth': data.get('place_of_birth', ''),
            'current_location': data.get('current_location', ''),
        })
        return jsonify({'success': True, 'person_id': person_uuid, 'family_groups': family_groups, 'message': 'Person added successfully'}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<string:person_uuid>', methods=['GET'])
@require_tree
def get_person(person_uuid, tree_uuid=None):
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    return jsonify({'success': True, 'id': person_uuid, 'person': record_to_person(record)}), 200


@app.route('/api/person/<string:person_uuid>', methods=['PUT'])
@require_tree
def update_person(person_uuid, tree_uuid=None):
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    data = request.json
    try:
        update_data = {}
        if 'first_name' in data:    update_data['first_name']    = data['first_name']
        if 'last_name' in data:     update_data['last_name']     = data['last_name']
        if 'middle_name' in data:   update_data['middle_name']   = data['middle_name']
        if 'nick_name' in data:     update_data['nick_name']     = data['nick_name']
        if 'sex' in data:           update_data['sex']           = data['sex'].upper()[0]
        if 'family_groups' in data: update_data['family_groups'] = data['family_groups']
        if 'birthday' in data:      update_data['birthday']      = data['birthday']
        if 'place_of_birth' in data:   update_data['place_of_birth']   = data['place_of_birth']
        if 'current_location' in data: update_data['current_location'] = data['current_location']
        if 'father_id' in data:     update_data['father_id']     = data['father_id'] or ''
        if 'mother_id' in data:     update_data['mother_id']     = data['mother_id'] or ''
        pb.collection('people').update(record.id, update_data)
        updated = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
        return jsonify({'success': True, 'message': 'Person updated successfully', 'person': record_to_person(updated)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<string:person_uuid>/position', methods=['PUT'])
@require_tree
def update_position(person_uuid, tree_uuid=None):
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    data = request.json
    try:
        pb.collection('people').update(record.id, {'pos_x': data.get('pos_x'), 'pos_y': data.get('pos_y')})
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<string:person_uuid>/parents', methods=['GET'])
@require_tree
def get_parents(person_uuid, tree_uuid=None):
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    parents = {'father': None, 'mother': None}
    if record.father_id:
        father = get_pb_record_by_person_uuid(record.father_id, tree_uuid)
        if father:
            parents['father'] = {'id': father.person_uuid, **record_to_person(father)}
    if record.mother_id:
        mother = get_pb_record_by_person_uuid(record.mother_id, tree_uuid)
        if mother:
            parents['mother'] = {'id': mother.person_uuid, **record_to_person(mother)}
    return jsonify({'success': True, 'parents': parents}), 200


@app.route('/api/person/<string:person_uuid>/children', methods=['GET'])
@require_tree
def get_children(person_uuid, tree_uuid=None):
    try:
        records = pb.collection('people').get_full_list(
            query_params={'filter': f'tree_id="{tree_uuid}" && (father_id="{person_uuid}" || mother_id="{person_uuid}")'}
        )
        children = [{'id': r.person_uuid, **record_to_person(r)} for r in records]
        return jsonify({'success': True, 'children': children, 'count': len(children)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<string:person_uuid>/siblings', methods=['GET'])
@require_tree
def get_siblings(person_uuid, tree_uuid=None):
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    try:
        people_records = get_people_for_tree(tree_uuid)
        graph = build_graph(people_records)
        siblings = set()
        for parent_id in [record.father_id, record.mother_id]:
            if parent_id and graph.has_node(parent_id):
                for child_id in graph.successors(parent_id):
                    if child_id != person_uuid:
                        siblings.add(child_id)
        sibling_list = []
        for sibling_uuid in siblings:
            sibling_record = get_pb_record_by_person_uuid(sibling_uuid, tree_uuid)
            if sibling_record:
                sibling_list.append({'id': sibling_uuid, **record_to_person(sibling_record)})
        return jsonify({'success': True, 'siblings': sibling_list, 'count': len(sibling_list)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<string:person_uuid>/auntsuncles', methods=['GET'])
@require_tree
def get_aunts_uncles(person_uuid, tree_uuid=None):
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    try:
        people_records = get_people_for_tree(tree_uuid)
        graph = build_graph(people_records)

        # Find blood aunts/uncles — parents' siblings
        aunts_uncles = set()
        for parent_id in [record.father_id, record.mother_id]:
            if parent_id and graph.has_node(parent_id):
                for grandparent_id in graph.predecessors(parent_id):
                    for aunt_uncle_id in graph.successors(grandparent_id):
                        if aunt_uncle_id != parent_id:
                            aunts_uncles.add(aunt_uncle_id)

        # Find spouses of blood aunts/uncles
        # A spouse is someone who shares a child with the aunt/uncle
        # but is not themselves an aunt/uncle by blood
        spouses = set()
        for au_id in aunts_uncles:
            for child_id in graph.successors(au_id):
                for co_parent_id in graph.predecessors(child_id):
                    if co_parent_id != au_id and co_parent_id not in aunts_uncles:
                        spouses.add(co_parent_id)

        all_aunts_uncles = aunts_uncles | spouses

        result = []
        for au_uuid in all_aunts_uncles:
            au_record = get_pb_record_by_person_uuid(au_uuid, tree_uuid)
            if au_record:
                result.append({'id': au_uuid, **record_to_person(au_record)})

        return jsonify({'success': True, 'aunts_uncles': result, 'count': len(result)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<string:person_uuid>/grandparents', methods=['GET'])
@require_tree
def get_grandparents(person_uuid, tree_uuid=None):
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    try:
        people_records = get_people_for_tree(tree_uuid)
        graph = build_graph(people_records)
        grandparents = set()
        for parent_id in [record.father_id, record.mother_id]:
            if parent_id and graph.has_node(parent_id):
                for grandparent_id in graph.predecessors(parent_id):
                    grandparents.add(grandparent_id)
        result = []
        for gp_uuid in grandparents:
            gp_record = get_pb_record_by_person_uuid(gp_uuid, tree_uuid)
            if gp_record:
                result.append({'id': gp_uuid, **record_to_person(gp_record)})
        return jsonify({'success': True, 'grandparents': result, 'count': len(result)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<string:person_uuid>/cousins', methods=['GET'])
@require_tree
def get_cousins(person_uuid, tree_uuid=None):
    print(f"[DEBUG] get_cousins called: person_uuid={person_uuid}, tree_uuid={tree_uuid}")
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404
    try:
        people_records = get_people_for_tree(tree_uuid)
        graph = build_graph(people_records)
        siblings = set()
        for parent_id in [record.father_id, record.mother_id]:
            if parent_id and graph.has_node(parent_id):
                for child_id in graph.successors(parent_id):
                    if child_id != person_uuid:
                        siblings.add(child_id)
        aunts_uncles = set()
        for parent_id in [record.father_id, record.mother_id]:
            if parent_id and graph.has_node(parent_id):
                for grandparent_id in graph.predecessors(parent_id):
                    for aunt_uncle_id in graph.successors(grandparent_id):
                        if aunt_uncle_id != parent_id:
                            aunts_uncles.add(aunt_uncle_id)
        cousins = set()
        for aunt_uncle_id in aunts_uncles:
            for cousin_id in graph.successors(aunt_uncle_id):
                if cousin_id != person_uuid and cousin_id not in siblings:
                    cousins.add(cousin_id)
        cousin_list = []
        for cousin_uuid in cousins:
            cousin_record = get_pb_record_by_person_uuid(cousin_uuid, tree_uuid)
            if cousin_record:
                cousin_list.append({'id': cousin_uuid, **record_to_person(cousin_record)})
        return jsonify({'success': True, 'cousins': cousin_list, 'count': len(cousin_list)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ─────────────────────────────────────────────
# People endpoint
# ─────────────────────────────────────────────

@app.route('/api/people', methods=['GET'])
@require_tree
def get_all_people(tree_uuid=None):
    records = get_people_for_tree(tree_uuid)
    people  = [{'id': r.person_uuid, **record_to_person(r)} for r in records]
    return jsonify({'success': True, 'people': people, 'count': len(people)}), 200


# ─────────────────────────────────────────────
# Generation endpoint
# ─────────────────────────────────────────────

@app.route('/api/people/generations', methods=['GET'])
@require_tree
def get_generations(tree_uuid=None):
    records    = get_people_for_tree(tree_uuid)
    graph      = build_graph(records)
    generation = {}
    roots      = [n for n in graph.nodes if graph.in_degree(n) == 0]
    queue      = list(roots)
    for r in roots:
        generation[r] = 0
    while queue:
        current = queue.pop(0)
        for child in graph.successors(current):
            parent_gen = max(generation[p] for p in graph.predecessors(child) if p in generation)
            new_gen    = parent_gen + 1
            if child not in generation or generation[child] < new_gen:
                generation[child] = new_gen
                queue.append(child)
    result  = [{'id': r.person_uuid, 'first_name': r.first_name, 'last_name': r.last_name, 'generation': generation.get(r.person_uuid, 0)} for r in records]
    max_gen = max((r['generation'] for r in result), default=0)
    return jsonify({'success': True, 'people': result, 'max_generation': max_gen}), 200


# ─────────────────────────────────────────────
# Group endpoints
# ─────────────────────────────────────────────

@app.route('/api/groups', methods=['GET'])
@require_tree
def get_all_groups(tree_uuid=None):
    records = get_people_for_tree(tree_uuid)
    groups  = {}
    for record in records:
        for group_id in (record.family_groups or []):
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append({'id': record.person_uuid, **record_to_person(record)})
    return jsonify({'success': True, 'groups': groups, 'count': len(groups)}), 200


@app.route('/api/group/<int:group_id>', methods=['GET'])
@require_tree
def get_group(group_id, tree_uuid=None):
    records = get_people_for_tree(tree_uuid)
    members = [{'id': r.person_uuid, **record_to_person(r)} for r in records if group_id in (r.family_groups or [])]
    if not members:
        return jsonify({'success': False, 'error': 'Group not found'}), 404
    return jsonify({'success': True, 'group_id': group_id, 'members': members, 'count': len(members)}), 200


# ─────────────────────────────────────────────
# Export and stats
# ─────────────────────────────────────────────

@app.route('/api/export', methods=['GET'])
@require_tree
def export_tree(tree_uuid=None):
    records = get_people_for_tree(tree_uuid)
    nodes   = [{'id': r.person_uuid, **record_to_person(r)} for r in records]
    edges   = []
    for r in records:
        if r.father_id:
            edges.append({'source': r.father_id, 'target': r.person_uuid, 'relation': 'father'})
        if r.mother_id:
            edges.append({'source': r.mother_id, 'target': r.person_uuid, 'relation': 'mother'})
    return jsonify({'success': True, 'tree': {'nodes': nodes, 'edges': edges}}), 200


@app.route('/api/stats', methods=['GET'])
@require_tree
def get_stats(tree_uuid=None):
    records    = get_people_for_tree(tree_uuid)
    graph      = build_graph(records)
    all_groups = {g for _, d in graph.nodes(data=True) for g in d.get('family_groups', [])}
    return jsonify({'success': True, 'stats': {
        'total_people':        graph.number_of_nodes(),
        'total_relationships': graph.number_of_edges(),
        'total_groups':        len(all_groups)
    }}), 200


# ─────────────────────────────────────────────
# API index
# ─────────────────────────────────────────────

@app.route('/api', methods=['GET'])
def api_index():
    return jsonify({
        'name':    'Family Tree REST API',
        'version': '2.0',
        'endpoints': {
            'POST /api/tree/enter':              'Validate access code and get tree info',
            'GET /api/familygroups':             'Get all named family groups',
            'POST /api/familygroup':             'Create a named family group',
            'PUT /api/familygroup/<uuid>':       'Rename/recolor a family group',
            'DELETE /api/familygroup/<uuid>':    'Delete a family group',
            'POST /api/person':                  'Add a new person',
            'GET /api/person/<id>':              'Get person details',
            'PUT /api/person/<id>':              'Update person details',
            'PUT /api/person/<id>/position':     'Update person canvas position',
            'GET /api/person/<id>/parents':      'Get parents of a person',
            'GET /api/person/<id>/grandparents': 'Get grandparents of a person',
            'GET /api/person/<id>/children':     'Get children of a person',
            'GET /api/person/<id>/siblings':     'Get siblings of a person',
            'GET /api/person/<id>/auntsuncles':  'Get aunts and uncles of a person',
            'GET /api/person/<id>/cousins':      'Get first cousins of a person',
            'GET /api/people':                   'Get all people',
            'GET /api/people/generations':       'Get generation depth for each person',
            'GET /api/groups':                   'Get all family groups',
            'GET /api/group/<id>':               'Get members of a specific group',
            'GET /api/export':                   'Export family tree',
            'GET /api/stats':                    'Get tree statistics'
        }
    }), 200


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)