import uuid
import json
from functools import wraps
from typing import Optional, Dict, Any

import networkx as nx
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pocketbase import PocketBase

app = Flask(__name__)
CORS(app)

pb = PocketBase('https://pocketbase.tail32217.ts.net')

# ─────────────────────────────────────────────
# PocketBase helpers
# ─────────────────────────────────────────────

def get_tree_by_access_code(access_code: str) -> Optional[Dict]:
    """Look up a tree record by access code. Returns the record or None."""
    try:
        print(f"[DEBUG] Looking up access_code: '{access_code}'")
        result = pb.collection('trees').get_full_list(
            query_params={'filter': f'access_code="{access_code}"'}
        )
        print(f"[DEBUG] PocketBase returned {len(result)} record(s)")
        if result:
            print(f"[DEBUG] First record: {result[0].__dict__}")
            return result[0]
        return None
    except Exception as e:
        print(f"[DEBUG] Exception during lookup: {e}")
        return None


def get_people_for_tree(tree_uuid: str) -> list:
    """Fetch all people belonging to a tree."""
    try:
        records = pb.collection('people').get_full_list(
            query_params={'filter': f'tree_id="{tree_uuid}"'}
        )
        return records
    except Exception:
        return []


def record_to_person(record) -> Dict[str, Any]:
    """Convert a PocketBase people record to a person dict."""
    return {
        'first_name': record.first_name,
        'last_name': record.last_name,
        'middle_name': getattr(record, 'middle_name', None) or None,
        'nick_name': getattr(record, 'nick_name', None) or None,
        'sex': record.sex,
        'family_groups': record.family_groups or [],
        'father_id': record.father_id or None,
        'mother_id': record.mother_id or None,
        'birthday': record.birthday or None,
        'place_of_birth': record.place_of_birth or None,
        'current_location': record.current_location or None,
        'pos_x': getattr(record, 'pos_x', None),
        'pos_y': getattr(record, 'pos_y', None),
    }


def build_graph(people_records: list) -> nx.DiGraph:
    """Build a NetworkX graph from a list of PocketBase people records."""
    graph = nx.DiGraph()

    for record in people_records:
        graph.add_node(
            record.person_uuid,
            **record_to_person(record)
        )

    for record in people_records:
        if record.father_id and graph.has_node(record.father_id):
            graph.add_edge(record.father_id, record.person_uuid, relation='father')
        if record.mother_id and graph.has_node(record.mother_id):
            graph.add_edge(record.mother_id, record.person_uuid, relation='mother')

    return graph


def get_pb_record_by_person_uuid(person_uuid: str, tree_uuid: str):
    """Fetch a single PocketBase people record by person_uuid and tree_uuid."""
    try:
        return pb.collection('people').get_first_list_item(
            f'person_uuid="{person_uuid}" && tree_id="{tree_uuid}"'
        )
    except Exception:
        return None


# ─────────────────────────────────────────────
# Auth middleware
# ─────────────────────────────────────────────

def require_tree(f):
    """Decorator that validates X-Access-Code and injects tree_uuid into kwargs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        access_code = request.headers.get('X-Access-Code')
        if not access_code:
            return jsonify({'success': False, 'error': 'Missing X-Access-Code header'}), 401

        tree = get_tree_by_access_code(access_code)
        if not tree:
            return jsonify({'success': False, 'error': 'Invalid access code'}), 403

        kwargs['tree_uuid'] = tree.tree_uuid
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# Tree endpoint
# ─────────────────────────────────────────────

@app.route('/api/tree/enter', methods=['POST'])
def enter_tree():
    """
    Validate an access code and return tree metadata.

    Request body:
    {
        "access_code": "your-uuid-here"
    }
    """
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
            'tree_uuid': tree.tree_uuid,
            'name': tree.name,
            'description': tree.description or ''
        }
    }), 200


# ─────────────────────────────────────────────
# Person endpoints
# ─────────────────────────────────────────────

@app.route('/api/person', methods=['POST'])
@require_tree
def add_person(tree_uuid=None):
    """
    Add a new person to the family tree.

    Request body:
    {
        "name": "John Doe",
        "sex": "male",
        "father_id": "person-uuid-optional",
        "mother_id": "person-uuid-optional",
        "family_groups": [1, 2],
        "birthday": "1980-01-01",
        "place_of_birth": "Boston",
        "current_location": "New York"
    }
    """
    data = request.json

    try:
        people_records = get_people_for_tree(tree_uuid)
        graph = build_graph(people_records)

        father_id = data.get('father_id')
        mother_id = data.get('mother_id')

        # Determine family groups
        family_groups = data.get('family_groups')
        if not family_groups:
            inherited = set()
            if father_id and graph.has_node(father_id):
                inherited.update(graph.nodes[father_id].get('family_groups', []))
            if mother_id and graph.has_node(mother_id):
                inherited.update(graph.nodes[mother_id].get('family_groups', []))
            if inherited:
                family_groups = list(inherited)
            else:
                # Assign next available group ID
                all_groups = [
                    g for _, d in graph.nodes(data=True)
                    for g in d.get('family_groups', [])
                ]
                family_groups = [(max(all_groups) + 1) if all_groups else 1]

        person_uuid = str(uuid.uuid4())
        sex = data['sex'].lower()

        pb.collection('people').create({
            'tree_id': tree_uuid,
            'person_uuid': person_uuid,
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'middle_name': data.get('middle_name', ''),
            'nick_name': data.get('nick_name', ''),
            'sex': data['sex'].upper()[0],
            'family_groups': family_groups,
            'father_id': father_id or '',
            'mother_id': mother_id or '',
            'birthday': data.get('birthday', ''),
            'place_of_birth': data.get('place_of_birth', ''),
            'current_location': data.get('current_location', ''),
        })

        return jsonify({
            'success': True,
            'person_id': person_uuid,
            'family_groups': family_groups,
            'message': 'Person added successfully'
        }), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<person_uuid>', methods=['GET'])
@require_tree
def get_person(person_uuid, tree_uuid=None):
    """Get information about a specific person."""
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)

    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404

    return jsonify({
        'success': True,
        'id': person_uuid,
        'person': record_to_person(record)
    }), 200


@app.route('/api/person/<person_uuid>', methods=['PUT'])
@require_tree
def update_person(person_uuid, tree_uuid=None):
    """
    Update a person's details.

    Request body:
    {
        "name": "John Doe",
        "sex": "male",
        "father_id": "person-uuid-optional",
        "mother_id": "person-uuid-optional",
        "family_groups": [1, 2],
        "birthday": "1980-01-01",
        "place_of_birth": "Boston",
        "current_location": "New York"
    }
    """
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404

    data = request.json

    try:
        update_data = {}

        if 'first_name' in data:
            update_data['first_name'] = data['first_name']
        if 'last_name' in data:
            update_data['last_name'] = data['last_name']
        if 'middle_name' in data:
            update_data['middle_name'] = data['middle_name']
        if 'nick_name' in data:
            update_data['nick_name'] = data['nick_name']
        if 'sex' in data:
            update_data['sex'] = data['sex'].upper()[0]  # 'M' or 'F'
        if 'family_groups' in data:
            update_data['family_groups'] = data['family_groups']
        if 'birthday' in data:
            update_data['birthday'] = data['birthday']
        if 'place_of_birth' in data:
            update_data['place_of_birth'] = data['place_of_birth']
        if 'current_location' in data:
            update_data['current_location'] = data['current_location']
        if 'father_id' in data:
            update_data['father_id'] = data['father_id'] or ''
        if 'mother_id' in data:
            update_data['mother_id'] = data['mother_id'] or ''

        pb.collection('people').update(record.id, update_data)

        updated = get_pb_record_by_person_uuid(person_uuid, tree_uuid)

        return jsonify({
            'success': True,
            'message': 'Person updated successfully',
            'person': record_to_person(updated)
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<person_uuid>/position', methods=['PUT'])
@require_tree
def update_position(person_uuid, tree_uuid=None):
    """
    Update a person's canvas position.

    Request body:
    {
        "pos_x": 123.45,
        "pos_y": 678.90
    }
    """
    record = get_pb_record_by_person_uuid(person_uuid, tree_uuid)
    if not record:
        return jsonify({'success': False, 'error': 'Person not found'}), 404

    data = request.json

    try:
        pb.collection('people').update(record.id, {
            'pos_x': data.get('pos_x'),
            'pos_y': data.get('pos_y'),
        })
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<person_uuid>/parents', methods=['GET'])
@require_tree
def get_parents(person_uuid, tree_uuid=None):
    """Get the parents of a person."""
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


@app.route('/api/person/<person_uuid>/children', methods=['GET'])
@require_tree
def get_children(person_uuid, tree_uuid=None):
    """Get all children of a person."""
    try:
        records = pb.collection('people').get_full_list(
            query_params={
                'filter': f'tree_id="{tree_uuid}" && (father_id="{person_uuid}" || mother_id="{person_uuid}")'
            }
        )

        children = [{'id': r.person_uuid, **record_to_person(r)} for r in records]

        return jsonify({'success': True, 'children': children, 'count': len(children)}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/person/<person_uuid>/siblings', methods=['GET'])
@require_tree
def get_siblings(person_uuid, tree_uuid=None):
    """Get all siblings of a person (share at least one parent)."""
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


# ─────────────────────────────────────────────
# People endpoint
# ─────────────────────────────────────────────

@app.route('/api/people', methods=['GET'])
@require_tree
def get_all_people(tree_uuid=None):
    """Get all people in the family tree."""
    records = get_people_for_tree(tree_uuid)

    people = [{'id': r.person_uuid, **record_to_person(r)} for r in records]

    return jsonify({'success': True, 'people': people, 'count': len(people)}), 200


# ─────────────────────────────────────────────
# Group endpoints
# ─────────────────────────────────────────────

@app.route('/api/groups', methods=['GET'])
@require_tree
def get_all_groups(tree_uuid=None):
    """Get all family groups."""
    records = get_people_for_tree(tree_uuid)

    groups = {}
    for record in records:
        for group_id in (record.family_groups or []):
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append({'id': record.person_uuid, **record_to_person(record)})

    return jsonify({'success': True, 'groups': groups, 'count': len(groups)}), 200


@app.route('/api/group/<int:group_id>', methods=['GET'])
@require_tree
def get_group(group_id, tree_uuid=None):
    """Get all people in a specific family group."""
    records = get_people_for_tree(tree_uuid)

    members = [
        {'id': r.person_uuid, **record_to_person(r)}
        for r in records
        if group_id in (r.family_groups or [])
    ]

    if not members:
        return jsonify({'success': False, 'error': 'Group not found'}), 404

    return jsonify({'success': True, 'group_id': group_id, 'members': members, 'count': len(members)}), 200


# ─────────────────────────────────────────────
# Export and stats endpoints
# ─────────────────────────────────────────────

@app.route('/api/export', methods=['GET'])
@require_tree
def export_tree(tree_uuid=None):
    """Export the entire family tree as JSON."""
    records = get_people_for_tree(tree_uuid)

    nodes = [{'id': r.person_uuid, **record_to_person(r)} for r in records]

    edges = []
    for r in records:
        if r.father_id:
            edges.append({'source': r.father_id, 'target': r.person_uuid, 'relation': 'father'})
        if r.mother_id:
            edges.append({'source': r.mother_id, 'target': r.person_uuid, 'relation': 'mother'})

    return jsonify({'success': True, 'tree': {'nodes': nodes, 'edges': edges}}), 200


@app.route('/api/stats', methods=['GET'])
@require_tree
def get_stats(tree_uuid=None):
    """Get statistics about the family tree."""
    records = get_people_for_tree(tree_uuid)
    graph = build_graph(records)

    all_groups = {
        g for _, d in graph.nodes(data=True)
        for g in d.get('family_groups', [])
    }

    return jsonify({
        'success': True,
        'stats': {
            'total_people': graph.number_of_nodes(),
            'total_relationships': graph.number_of_edges(),
            'total_groups': len(all_groups)
        }
    }), 200


# ─────────────────────────────────────────────
# API index
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    """Serve the main family tree page."""
    return render_template('index.html')


@app.route('/landing', methods=['GET'])
def landing():
    """Serve the landing page."""
    return render_template('landing.html')


# ─────────────────────────────────────────────
# API index
# ─────────────────────────────────────────────

@app.route('/api', methods=['GET'])
def api_index():
    """API documentation."""
    return jsonify({
        'name': 'Family Tree REST API',
        'version': '2.0',
        'endpoints': {
            'POST /api/tree/enter': 'Validate access code and get tree info',
            'POST /api/person': 'Add a new person',
            'GET /api/person/<id>': 'Get person details',
            'PUT /api/person/<id>': 'Update person details',
            'PUT /api/person/<id>/position': 'Update person canvas position',
            'GET /api/person/<id>/parents': 'Get parents of a person',
            'GET /api/person/<id>/children': 'Get children of a person',
            'GET /api/person/<id>/siblings': 'Get siblings of a person',
            'GET /api/people': 'Get all people',
            'GET /api/groups': 'Get all family groups',
            'GET /api/group/<id>': 'Get members of a specific group',
            'GET /api/export': 'Export family tree',
            'GET /api/stats': 'Get tree statistics'
        }
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)