from bson import ObjectId

def serialize_document(doc):
    doc['_id'] = str(doc['_id'])
    return doc
