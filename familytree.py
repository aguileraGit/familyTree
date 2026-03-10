import networkx as nx
import uuid
import json
from typing import Optional, Dict, Any

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
        """
        Add a person to the family tree.
        
        Args:
            name: Person's name
            sex: 'male' or 'female'
            father_id: UUID of father (if known)
            mother_id: UUID of mother (if known)
            birthday: Date of birth (string format)
            place_of_birth: Place of birth
            current_location: Current location
        
        Returns:
            person_id: Unique UUID for the person
        """
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
        """Get all siblings of a person (people who share at least one parent)."""
        parents = self.get_parents(person_id)
        siblings = set()
        
        for parent_id in [parents['father'], parents['mother']]:
            if parent_id:
                for child_id in self.get_children(parent_id):
                    if child_id != person_id:
                        siblings.add(child_id)
        
        return list(siblings)
    
    def export_to_json(self, filepath: str):
        """
        Export the family tree to a JSON file.
        
        Args:
            filepath: Path to the output JSON file
        """
        data = {
            'nodes': [],
            'edges': []
        }
        
        # Export nodes with their attributes
        for node_id, attrs in self.graph.nodes(data=True):
            node_data = {'id': node_id}
            node_data.update(attrs)
            data['nodes'].append(node_data)
        
        # Export edges with their attributes
        for source, target, attrs in self.graph.edges(data=True):
            edge_data = {
                'source': source,
                'target': target
            }
            edge_data.update(attrs)
            data['edges'].append(edge_data)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def import_from_json(self, filepath: str):
        """
        Import a family tree from a JSON file.
        
        Args:
            filepath: Path to the input JSON file
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Clear existing graph
        self.graph.clear()
        
        # Import nodes
        for node_data in data['nodes']:
            node_id = node_data.pop('id')
            self.graph.add_node(node_id, **node_data)
        
        # Import edges
        for edge_data in data['edges']:
            source = edge_data.pop('source')
            target = edge_data.pop('target')
            self.graph.add_edge(source, target, **edge_data)
    
    def export_to_json_string(self) -> str:
        """
        Export the family tree to a JSON string.
        
        Returns:
            JSON string representation of the family tree
        """
        data = {
            'nodes': [],
            'edges': []
        }
        
        # Export nodes with their attributes
        for node_id, attrs in self.graph.nodes(data=True):
            node_data = {'id': node_id}
            node_data.update(attrs)
            data['nodes'].append(node_data)
        
        # Export edges with their attributes
        for source, target, attrs in self.graph.edges(data=True):
            edge_data = {
                'source': source,
                'target': target
            }
            edge_data.update(attrs)
            data['edges'].append(edge_data)
        
        return json.dumps(data, indent=2)
    
    def import_from_json_string(self, json_string: str):
        """
        Import a family tree from a JSON string.
        
        Args:
            json_string: JSON string representation of the family tree
        """
        data = json.loads(json_string)
        
        # Clear existing graph
        self.graph.clear()
        
        # Import nodes
        for node_data in data['nodes']:
            node_id = node_data.pop('id')
            self.graph.add_node(node_id, **node_data)
        
        # Import edges
        for edge_data in data['edges']:
            source = edge_data.pop('source')
            target = edge_data.pop('target')
            self.graph.add_edge(source, target, **edge_data)
    
    def print_person(self, person_id: str):
        """Print detailed information about a person."""
        person = self.get_person(person_id)
        if not person:
            print(f"Person {person_id} not found")
            return
        
        print(f"\n--- Person ID: {person_id} ---")
        print(f"Name: {person['name']}")
        print(f"Sex: {'Male' if person['male'] else 'Female'}")
        
        if person.get('birthday'):
            print(f"Birthday: {person['birthday']}")
        if person.get('place_of_birth'):
            print(f"Place of Birth: {person['place_of_birth']}")
        if person.get('current_location'):
            print(f"Current Location: {person['current_location']}")
        
        parents = self.get_parents(person_id)
        if parents['father']:
            father = self.get_person(parents['father'])
            print(f"Father: {father['name']}")
        if parents['mother']:
            mother = self.get_person(parents['mother'])
            print(f"Mother: {mother['name']}")
        
        children = self.get_children(person_id)
        if children:
            print(f"Children: {len(children)}")
            for child_id in children:
                child = self.get_person(child_id)
                print(f"  - {child['name']}")
        
        siblings = self.get_siblings(person_id)
        if siblings:
            print(f"Siblings: {len(siblings)}")
            for sibling_id in siblings:
                sibling = self.get_person(sibling_id)
                print(f"  - {sibling['name']}")


# Example usage
if __name__ == "__main__":
    tree = FamilyTree()
    
    # Add parents
    john_id = tree.add_person(
        name="John Smith",
        sex="male",
        birthday="1980-03-10",
        place_of_birth="Boston",
        current_location="New York"
    )
    
    jane_id = tree.add_person(
        name="Jane Smith",
        sex="female",
        birthday="1982-07-20",
        place_of_birth="Chicago",
        current_location="New York"
    )
    
    # Add children
    alice_id = tree.add_person(
        name="Alice Smith",
        sex="female",
        father_id=john_id,
        mother_id=jane_id,
        birthday="2010-05-15",
        current_location="New York"
    )
    
    bob_id = tree.add_person(
        name="Bob Smith",
        sex="male",
        father_id=john_id,
        mother_id=jane_id,
        birthday="2012-08-22",
        current_location="New York"
    )
    
    # Print family members
    print("=" * 50)
    print("FAMILY TREE EXAMPLE")
    print("=" * 50)
    
    tree.print_person(john_id)
    tree.print_person(jane_id)
    tree.print_person(alice_id)
    tree.print_person(bob_id)
    
    print(f"\nTotal people in tree: {tree.graph.number_of_nodes()}")
    
    # Export to JSON file
    print("\n" + "=" * 50)
    print("EXPORTING TO JSON")
    print("=" * 50)
    tree.export_to_json("family_tree.json")
    print("Family tree exported to 'family_tree.json'")
    
    # Export to JSON string (for demonstration)
    json_str = tree.export_to_json_string()
    print("\nJSON representation (first 500 chars):")
    print(json_str[:500] + "...")
    
    # Import from JSON file
    print("\n" + "=" * 50)
    print("IMPORTING FROM JSON")
    print("=" * 50)
    new_tree = FamilyTree()
    new_tree.import_from_json("family_tree.json")
    print(f"Imported tree has {new_tree.graph.number_of_nodes()} people")
    
    # Verify import worked
    print("\nVerifying import - John's children:")
    for child_id in new_tree.get_children(john_id):
        child = new_tree.get_person(child_id)
        print(f"  - {child['name']}")
