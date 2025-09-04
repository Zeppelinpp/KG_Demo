## Cypher

### `apoc.meta.relTypeProperties`
```
CALL apoc.meta.relTypeProperties
```
```json
[
    {
        'relType': ':`LIKES`', 
        'sourceNodeLabels': ['Person'], 
        'targetNodeLabels': ['Movie'], 
        'propertyName': None, 
        'propertyTypes': None, 
        'mandatory': False, 
        'propertyObservations': 0, 
        'totalObservations': 2
    }, 
    {
        'relType': ':`KNOWS`', 
        'sourceNodeLabels': ['Person'], 
        'targetNodeLabels': ['Person'], 
        'propertyName': None, 
        'propertyTypes': None, 
        'mandatory': False, 
        'propertyObservations': 0, 
        'totalObservations': 2
    }
]
```
