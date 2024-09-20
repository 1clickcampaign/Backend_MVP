import spacy

nlp = spacy.load('en_core_web_sm')

def parse_query(query):
    doc = nlp(query)
    business_type = None
    location = None

    locations = [ent.text for ent in doc.ents if ent.label_ in ('GPE', 'LOC')]
    if locations:
        location = locations[0]

    business_phrases = [
        chunk.text for chunk in doc.noun_chunks
        if chunk.root.ent_type_ not in ('GPE', 'LOC') and chunk.root.pos_ != 'PRON'
    ]
    if business_phrases:
        business_type = business_phrases[0]

    return business_type, location
