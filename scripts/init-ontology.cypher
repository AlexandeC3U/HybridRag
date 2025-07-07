// Import the ontology (Turtle format)
CALL n10s.onto.import.fetch('file:///app/uns_ontology.ttl', 'Turtle');

// Map ontology classes to graph labels
CALL n10s.mapping.add('http://example.org/uns#Site', 'Site');
CALL n10s.mapping.add('http://example.org/uns#Area', 'Area');
CALL n10s.mapping.add('http://example.org/uns#Line', 'Line');
CALL n10s.mapping.add('http://example.org/uns#Machine', 'Machine');
CALL n10s.mapping.add('http://example.org/uns#Sensor', 'Sensor');
CALL n10s.mapping.add('http://example.org/uns#Asset', 'Asset'); 