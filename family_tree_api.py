import networkx as nx
import uuid
import json
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

CORS(app)  # Enable CORS for all routes

class FamilyTree:
    def __init__(self):
        self.graph = nx.DiGraph()
    
    def add_person(
        self,
        name: str,
        sex: str,
        father_id: Optional[str] = None,
        mother_id: Optional[str] = None,
        birthday: Optional[str] = None,
        place_of_birth: Optional[str] = None,
        current_location: Optional[str] = None
    ) -> str:
        """Add a person to the family tree."""
        person_id = str(uuid.uuid4())
        
        # Add node with attributes
        self.graph.add_node(
            person_id,
            name=name,
            male=sex.lower() == 'male',
            female=sex.lower() == 'female',
            birthday=birthday,
            place_of_birth=place_of_birth,
            current_location=current_location
        )
        
        # Add edges to parents
        if father_id and self.graph.has_node(father_id):
            self.graph.add_edge(father_id, person_id, relation='father')
        
        if mother_id and self.graph.has_node(mother_id):
            self.graph.add_edge(mother_id, person_id, relation='mother')
        
        return person_id
    
    def get_person(self, person_id: str) -> Dict[str, Any]:
        """Get all information about a person."""
        if not self.graph.has_node(person_id):
            return None
        return dict(self.graph.nodes[person_id])
    
    def get_parents(self, person_id: str) -> Dict[str, Optional[str]]:
        """Get the parents of a person."""
        parents = {'father': None, 'mother': None}
        
        for predecessor in self.graph.predecessors(person_id):
            edge_data = self.graph.edges[predecessor, person_id]
            if edge_data.get('relation') == 'father':
                parents['father'] = predecessor
            elif edge_data.get('relation') == 'mother':
                parents['mother'] = predecessor
        
        return parents
    
    def get_children(self, person_id: str) -> list[str]:
        """Get all children of a person."""
        return list(self.graph.successors(person_id))
    
    def get_siblings(self, person_id: str) -> list[str]:
        """Get all siblings of a person."""
        parents = self.get_parents(person_id)
        siblings = set()
        
        for parent_id in [parents['father'], parents['mother']]:
            if parent_id:
                for child_id in self.get_children(parent_id):
                    if child_id != person_id:
                        siblings.add(child_id)
        
        return list(siblings)
    
    def get_all_people(self) -> list[Dict[str, Any]]:
        """Get all people in the tree."""
        people = []
        for node_id, attrs in self.graph.nodes(data=True):
            person = {'id': node_id}
            person.update(attrs)
            people.append(person)
        return people
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export the family tree to a dictionary."""
        data = {
            'nodes': [],
            'edges': []
        }
        
        for node_id, attrs in self.graph.nodes(data=True):
            node_data = {'id': node_id}
            node_data.update(attrs)
            data['nodes'].append(node_data)
        
        for source, target, attrs in self.graph.edges(data=True):
            edge_data = {
                'source': source,
                'target': target
            }
            edge_data.update(attrs)
            data['edges'].append(edge_data)
        
        return data
    
    def import_from_dict(self, data: Dict[str, Any]):
        """Import a family tree from a dictionary."""
        self.graph.clear()
        
        for node_data in data['nodes']:
            node_id = node_data.pop('id')
            self.graph.add_node(node_id, **node_data)
        
        for edge_data in data['edges']:
            source = edge_data.pop('source')
            target = edge_data.pop('target')
            self.graph.add_edge(source, target, **edge_data)


# Global family tree instance
tree = FamilyTree()


# API Endpoints

@app.route('/api/person', methods=['POST'])
def add_person():
    """
    Add a new person to the family tree.
    
    Request body:
    {
        "name": "John Doe",
        "sex": "male",
        "father_id": "uuid-optional",
        "mother_id": "uuid-optional",
        "birthday": "1980-01-01",
        "place_of_birth": "Boston",
        "current_location": "New York"
    }
    """
    data = request.json
    
    try:
        person_id = tree.add_person(
            name=data['name'],
            sex=data['sex'],
            father_id=data.get('father_id'),
            mother_id=data.get('mother_id'),
            birthday=data.get('birthday'),
            place_of_birth=data.get('place_of_birth'),
            current_location=data.get('current_location')
        )
        
        return jsonify({
            'success': True,
            'person_id': person_id,
            'message': 'Person added successfully'
        }), 201
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/person/<person_id>', methods=['GET'])
def get_person(person_id):
    """Get information about a specific person."""
    person = tree.get_person(person_id)
    
    if person is None:
        return jsonify({
            'success': False,
            'error': 'Person not found'
        }), 404
    
    return jsonify({
        'success': True,
        'person': person,
        'id': person_id
    }), 200


@app.route('/api/person/<person_id>/parents', methods=['GET'])
def get_parents(person_id):
    """Get the parents of a person."""
    if not tree.graph.has_node(person_id):
        return jsonify({
            'success': False,
            'error': 'Person not found'
        }), 404
    
    parents = tree.get_parents(person_id)
    
    # Get full parent information
    parent_info = {}
    if parents['father']:
        parent_info['father'] = {
            'id': parents['father'],
            **tree.get_person(parents['father'])
        }
    else:
        parent_info['father'] = None
    
    if parents['mother']:
        parent_info['mother'] = {
            'id': parents['mother'],
            **tree.get_person(parents['mother'])
        }
    else:
        parent_info['mother'] = None
    
    return jsonify({
        'success': True,
        'parents': parent_info
    }), 200


@app.route('/api/person/<person_id>/children', methods=['GET'])
def get_children(person_id):
    """Get all children of a person."""
    if not tree.graph.has_node(person_id):
        return jsonify({
            'success': False,
            'error': 'Person not found'
        }), 404
    
    child_ids = tree.get_children(person_id)
    
    children = []
    for child_id in child_ids:
        children.append({
            'id': child_id,
            **tree.get_person(child_id)
        })
    
    return jsonify({
        'success': True,
        'children': children,
        'count': len(children)
    }), 200


@app.route('/api/person/<person_id>/siblings', methods=['GET'])
def get_siblings(person_id):
    """Get all siblings of a person."""
    if not tree.graph.has_node(person_id):
        return jsonify({
            'success': False,
            'error': 'Person not found'
        }), 404
    
    sibling_ids = tree.get_siblings(person_id)
    
    siblings = []
    for sibling_id in sibling_ids:
        siblings.append({
            'id': sibling_id,
            **tree.get_person(sibling_id)
        })
    
    return jsonify({
        'success': True,
        'siblings': siblings,
        'count': len(siblings)
    }), 200


@app.route('/api/people', methods=['GET'])
def get_all_people():
    """Get all people in the family tree."""
    people = tree.get_all_people()
    
    return jsonify({
        'success': True,
        'people': people,
        'count': len(people)
    }), 200


@app.route('/api/export', methods=['GET'])
def export_tree():
    """Export the entire family tree as JSON."""
    data = tree.export_to_dict()
    
    return jsonify({
        'success': True,
        'tree': data
    }), 200


@app.route('/api/import', methods=['POST'])
def import_tree():
    """
    Import a family tree from JSON.
    
    Request body:
    {
        "tree": {
            "nodes": [...],
            "edges": [...]
        }
    }
    """
    data = request.json
    
    try:
        tree.import_from_dict(data['tree'])
        
        return jsonify({
            'success': True,
            'message': 'Family tree imported successfully',
            'node_count': tree.graph.number_of_nodes()
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about the family tree."""
    return jsonify({
        'success': True,
        'stats': {
            'total_people': tree.graph.number_of_nodes(),
            'total_relationships': tree.graph.number_of_edges()
        }
    }), 200


@app.route('/', methods=['GET'])
def index():
    """API documentation."""
    return jsonify({
        'name': 'Family Tree REST API',
        'version': '1.0',
        'endpoints': {
            'POST /api/person': 'Add a new person',
            'GET /api/person/<id>': 'Get person details',
            'GET /api/person/<id>/parents': 'Get parents of a person',
            'GET /api/person/<id>/children': 'Get children of a person',
            'GET /api/person/<id>/siblings': 'Get siblings of a person',
            'GET /api/people': 'Get all people',
            'GET /api/export': 'Export family tree',
            'POST /api/import': 'Import family tree',
            'GET /api/stats': 'Get tree statistics'
        }
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='192.168.1.20', port=5000)
